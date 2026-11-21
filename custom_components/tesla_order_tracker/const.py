"""Constants for the Tesla Order Tracker."""
from datetime import timedelta
import logging

DOMAIN = "tesla_order_tracker"
PANEL = "tesla-order-tracker"
POLL_INTERVAL = timedelta(minutes=30)
AUTHORIZE = "https://auth.tesla.com/oauth2/v3/authorize"
TOKEN = "https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/token"
NORTH_AMERICA = "https://fleet-api.prd.na.vn.cloud.tesla.com"
EUROPE = "https://fleet-api.prd.eu.vn.cloud.tesla.com"
OWNER_HOST = "https://owner-api.teslamotors.com"
REGIONS = {"eu": EUROPE, "na": NORTH_AMERICA}
LOGGER = logging.getLogger(__package__)
FIELDS = {
    "model": "Model",
    "status": "Order status",
    "vin": "VIN",
    "delivery_window": "Delivery window",
    "delivery_center": "Delivery center",
    "appointment": "Delivery appointment",
    "production_status": "Production status",
}
