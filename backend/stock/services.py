from django.db import transaction
from decimal import Decimal
from .models import Product, StockMovement


class StockService:
    """
    Business logic for inventory/stock operations.
    """
    
    @staticmethod
    @transaction.atomic
    def adjust_stock(product, quantity, reason='adjustment', reference='', 
                    notes='', created_by=None):
        """
        Adjust product stock (can be positive or negative).
        
        Args:
            product: Product object
            quantity: Quantity to adjust (positive = increase, negative = decrease)
            reason: Reason for adjustment
            reference: Reference number/document
            notes: Additional notes
            created_by: User who made the adjustment
        """
        previous_stock = product.current_stock
        quantity_decimal = Decimal(str(quantity))
        
        product.current_stock += quantity_decimal
        product.save()
        
        # Create stock movement
        movement = StockMovement.objects.create(
            tenant=product.tenant,
            product=product,
            movement_type='adjustment',
            quantity=quantity_decimal,
            previous_stock=previous_stock,
            new_stock=product.current_stock,
            reference=reference,
            notes=notes,
            created_by=created_by
        )
        
        return movement
    
    @staticmethod
    @transaction.atomic
    def register_purchase(product, quantity, cost_price=None, reference='', 
                         notes='', created_by=None):
        """
        Register a purchase and update stock.
        """
        previous_stock = product.current_stock
        quantity_decimal = Decimal(str(quantity))
        
        product.current_stock += quantity_decimal
        
        # Update cost price if provided
        if cost_price is not None:
            product.cost_price = Decimal(str(cost_price))
        
        product.save()
        
        # Create stock movement
        movement = StockMovement.objects.create(
            tenant=product.tenant,
            product=product,
            movement_type='purchase',
            quantity=quantity_decimal,
            previous_stock=previous_stock,
            new_stock=product.current_stock,
            reference=reference,
            notes=notes,
            created_by=created_by
        )
        
        return movement
    
    @staticmethod
    def get_low_stock_products(tenant):
        """
        Get products with stock below minimum.
        """
        return Product.objects.filter(
            tenant=tenant,
            is_active=True,
            track_inventory=True,
            current_stock__lte=models.F('minimum_stock')
        )
