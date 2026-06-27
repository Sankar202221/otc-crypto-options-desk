from dash import Dash
from app.dashboard.layout import get_layout

# Initialize the Dash application
# It will be mounted on FastAPI under the /dashboard prefix
dash_app = Dash(
    __name__,
    requests_pathname_prefix="/dashboard/",
    assets_folder="assets",
    title="Crypto OTC Options Trading Desk"
)

# Bind layout
dash_app.layout = get_layout()

# Import callbacks to register them with the Dash application
import app.dashboard.callbacks
