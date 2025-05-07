"""
Order Processing Module
Handles order fulfillment, stock verification, and inventory updates
"""

from typing import Dict, List, Tuple
from dataclasses import dataclass
from tenacity import retry, stop_after_attempt, wait_random_exponential
from tqdm import tqdm
import time

@dataclass
class OrderItem:
    product_id: str
    requested_qty: int
    available_qty: int = 0

class OrderProcessor:
    def __init__(self, inventory_service, max_retries: int = 3):
        """
        Args:
            inventory_service: Service implementing get_product_stock(product_id)
            max_retries: Maximum attempts for stock checks
        """
        self.inventory = inventory_service
        self.max_retries = max_retries
        self.processed_orders = {}  # order_id: processed_items

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(multiplier=1, max=10),
        reraise=True
    )
    def _get_current_stock(self, product_id: str) -> int:
        """Get available stock with retry logic"""
        try:
            return self.inventory.get_product_stock(product_id)
        except Exception as e:
            print(f"Stock check failed for {product_id}: {e}")
            raise

    def _validate_order_item(self, product_id: str, requested_qty: int) -> Tuple[str, int]:
        """
        Validate single order line item
        
        Returns:
            Tuple of (status, available_qty)
            Status values: "available", "out_of_stock", "invalid_product"
        """
        if requested_qty <= 0:
            return ("invalid_quantity", 0)

        try:
            current_stock = self._get_current_stock(product_id)
            
            if current_stock is None:
                return ("invalid_product", 0)
                
            return (
                "available" if current_stock >= requested_qty else "partial",
                min(current_stock, requested_qty)
            )
            
        except Exception:
            return ("check_failed", 0)

    def process_order(self, order_id: str, items: List[Dict]) -> Dict:
        """
        Process complete order with multiple items
        
        Args:
            order_id: Unique order identifier
            items: List of {"product_id": str, "quantity": int}
            
        Returns:
            {
                "order_id": str,
                "status": "fulfilled"|"partial"|"failed",
                "items": [
                    {
                        "product_id": str,
                        "requested": int,
                        "fulfilled": int,
                        "status": str,
                        "remaining_stock": int
                    }
                ],
                "timestamp": str
            }
        """
        processed_items = []
        overall_status = "fulfilled"
        
        for item in tqdm(items, desc=f"Processing order {order_id}"):
            product_id = item["product_id"]
            requested_qty = item["quantity"]
            
            status, available_qty = self._validate_order_item(
                product_id, 
                requested_qty
            )
            
            # Update overall order status
            if status != "available":
                overall_status = "partial"
            if status == "invalid_product":
                overall_status = "failed"
            
            processed_items.append({
                "product_id": product_id,
                "requested": requested_qty,
                "fulfilled": available_qty,
                "status": status,
                "remaining_stock": self._get_current_stock(product_id) - available_qty
            })
            
            # Small delay between items
            time.sleep(0.1)
        
        result = {
            "order_id": order_id,
            "status": overall_status,
            "items": processed_items,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        self.processed_orders[order_id] = result
        return result

    def bulk_process(self, orders: Dict[str, List[Dict]], batch_size: int = 5) -> Dict:
        """
        Process multiple orders with rate limiting
        
        Args:
            orders: {order_id: [items]}
            batch_size: Parallel processing units
            
        Returns:
            {
                "success_count": int,
                "failed_count": int,
                "processed_orders": {order_id: results},
                "inventory_changes": {product_id: delta}
            }
        """
        summary = {
            "success_count": 0,
            "failed_count": 0,
            "processed_orders": {},
            "inventory_changes": {}
        }
        
        for order_id, items in tqdm(orders.items(), desc="Bulk processing"):
            try:
                result = self.process_order(order_id, items)
                summary["processed_orders"][order_id] = result
                
                if result["status"] == "fulfilled":
                    summary["success_count"] += 1
                else:
                    summary["failed_count"] += 1
                    
                # Track inventory changes
                for item in result["items"]:
                    product_id = item["product_id"]
                    delta = item["requested"] - item["fulfilled"]
                    summary["inventory_changes"][product_id] = (
                        summary["inventory_changes"].get(product_id, 0) + delta
                    )
                
            except Exception as e:
                summary["failed_count"] += 1
                summary["processed_orders"][order_id] = {
                    "error": str(e),
                    "status": "processing_error"
                }
            
            # Throttle processing
            if len(summary["processed_orders"]) % batch_size == 0:
                time.sleep(1)
        
        return summary

    def get_inventory_snapshot(self, product_ids: List[str]) -> Dict[str, int]:
        """Get current stock levels for multiple products"""
        return {
            pid: self._get_current_stock(pid)
            for pid in product_ids
        }