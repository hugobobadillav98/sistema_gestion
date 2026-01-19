from django.db import transaction
from decimal import Decimal, ROUND_HALF_UP
from .models import Sale, SaleItem
from stock.models import Product, StockMovement


class SaleService:
    """
    Business logic for sales operations.
    """
    
    @staticmethod
    @transaction.atomic
    def create_sale(tenant, items_data, customer=None, payment_method='cash', 
                   paid_amount=0, created_by=None, notes='',
                   currency_paid='PYG', paid_amount_original=0,
                   exchange_rate_usd=7300, exchange_rate_brl=1450,
                   pix_reference=''):
        """
        Create a new sale with items and update stock.
        
        Args:
            tenant: Tenant object
            items_data: List of dicts with {product_id, quantity, unit_price, discount_percent}
            customer: Customer object or None
            payment_method: Payment method choice
            paid_amount: Amount paid in PYG
            created_by: User who created the sale
            notes: Additional notes
            currency_paid: Currency used for payment (PYG, USD, BRL)
            paid_amount_original: Amount paid in original currency
            exchange_rate_usd: USD to PYG exchange rate
            exchange_rate_brl: BRL to PYG exchange rate
            pix_reference: PIX transaction ID
            
        Returns:
            Sale object
        """
        # Generate invoice number
        last_sale = Sale.objects.filter(tenant=tenant).order_by('-created_at').first()
        if last_sale and last_sale.invoice_number:
            try:
                last_number = int(last_sale.invoice_number.split('-')[-1])
                invoice_number = f"INV-{last_number + 1:06d}"
            except:
                invoice_number = f"INV-000001"
        else:
            invoice_number = f"INV-000001"
        
        # Create sale
        sale = Sale.objects.create(
            tenant=tenant,
            invoice_number=invoice_number,
            customer=customer,
            payment_method=payment_method,
            paid_amount=int(Decimal(str(paid_amount))),
            created_by=created_by,
            notes=notes,
            total_amount=0,  # Will be calculated
            subtotal=0,
            tax_amount=0,
            discount_amount=0,
            currency_paid=currency_paid,
            paid_amount_original=Decimal(str(paid_amount_original)),
            exchange_rate_usd=Decimal(str(exchange_rate_usd)),
            exchange_rate_brl=Decimal(str(exchange_rate_brl)),
            pix_reference=pix_reference,
            status='completed'
        )
        
        total_subtotal = Decimal('0')
        total_tax = Decimal('0')
        total_discount = Decimal('0')
        
        # Create sale items and update stock
        for item_data in items_data:
            product = Product.objects.get(
                id=item_data['product_id'],
                tenant=tenant
            )
            
            quantity = int(item_data['quantity'])
            unit_price = int(Decimal(str(item_data.get('unit_price', product.sale_price))))
            discount_percent = Decimal(str(item_data.get('discount_percent', 0)))
            
            # Create sale item
            sale_item = SaleItem(
                tenant=tenant,
                sale=sale,
                product=product,
                quantity=quantity,
                unit_price=unit_price,
                discount_percent=discount_percent,
                tax_type=product.tax_type  # ← Correcto: tax_type, no tax_rate
            )
            sale_item.calculate_totals()
            sale_item.save()
            
            total_subtotal += sale_item.subtotal
            total_tax += sale_item.tax_amount
            total_discount += sale_item.discount_amount
            
            # Update stock
            previous_stock = product.current_stock
            product.current_stock -= quantity
            product.save()
            
            # Create stock movement
            StockMovement.objects.create(
                tenant=tenant,
                product=product,
                movement_type='sale',
                quantity=quantity,
                previous_stock=previous_stock,  # ← AGREGAR
                new_stock=product.current_stock,  # ← AGREGAR
                reference=invoice_number,
                notes=f"Venta {invoice_number}",
                created_by=created_by
            )
        
        # Update sale totals
        sale.subtotal = int(total_subtotal)
        sale.tax_amount = int(total_tax)
        sale.discount_amount = int(total_discount)
        sale.total_amount = int(total_subtotal)
        
        # Calculate change
        if Decimal(str(paid_amount)) >= sale.total_amount:
            sale.change_amount = int(Decimal(str(paid_amount)) - sale.total_amount)
        
        # Update customer balance if on credit
        if payment_method == 'credit' and customer:
            customer.current_balance += sale.outstanding_balance
            customer.save()
        
        sale.save()
        
        return sale
    
    @staticmethod
    @transaction.atomic
    def cancel_sale(sale, cancelled_by=None):
        """
        Cancel a sale and restore stock.
        """
        if sale.status == 'cancelled':
            raise ValueError("Sale is already cancelled")
        
        # Restore stock
        for item in sale.items.all():
            previous_stock = item.product.current_stock
            item.product.current_stock += item.quantity
            item.product.save()
            
            # Create stock movement
            StockMovement.objects.create(
                tenant=sale.tenant,
                product=item.product,
                movement_type='adjustment',
                quantity=item.quantity,
                reference=f"CANCEL-{sale.invoice_number}",
                notes=f"Cancelación de venta {sale.invoice_number}",
                created_by=cancelled_by
            )
        
        # Update customer balance if was on credit
        if sale.customer and sale.payment_method == 'credit':
            sale.customer.current_balance -= sale.outstanding_balance
            sale.customer.save()
        
        sale.status = 'cancelled'
        sale.save()
        
        return sale
