import dash
import dash_bootstrap_components as dbc

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.FLATLY,
        "https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap",
    ],
    suppress_callback_exceptions=True,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}]
)
app.title = "TIBL ANALYTICS"
server = app.server

import os
from flask_caching import Cache

cache_type = os.getenv('CACHE_TYPE', 'SimpleCache')
cache_config = {
    'CACHE_TYPE': cache_type,
    'CACHE_DEFAULT_TIMEOUT': int(os.getenv('CACHE_DEFAULT_TIMEOUT', '300'))
}
if cache_type == 'RedisCache':
    cache_config['CACHE_REDIS_URL'] = os.getenv('CACHE_REDIS_URL', 'redis://localhost:6379/0')
elif cache_type == 'FileSystemCache':
    cache_config['CACHE_DIR'] = os.getenv('CACHE_DIR', 'cache-directory')

cache = Cache(app.server, config=cache_config)
