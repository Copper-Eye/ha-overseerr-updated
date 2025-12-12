"""Support for Overseerr."""
import logging
import voluptuous as vol
from datetime import timedelta

from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_PASSWORD,
    CONF_USERNAME,
    ATTR_ENTITY_ID
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.components import webhook
from homeassistant.helpers.service import ServiceCall, ServiceResponse, SupportsResponse

from .const import (
    DOMAIN,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_URLBASE,
    CONF_URLBASE,
    CONF_USERNAME,
    SERVICE_MOVIE_REQUEST,
    SERVICE_TV_REQUEST,
    SERVICE_SEARCH_MOVIE,
    SERVICE_SEARCH_TV,
    SERVICE_SEARCH,
    ATTR_NAME,
    ATTR_SEASON,
    ATTR_ID,
    ATTR_STATUS,
    ATTR_MEDIA_ID,
    SENSOR_TYPES,
)

from pyoverseerr import Overseerr

_LOGGER = logging.getLogger(__name__)

SUBMIT_MOVIE_REQUEST_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_NAME): cv.string,
    vol.Optional(ATTR_MEDIA_ID): cv.string,
})

SUBMIT_TV_REQUEST_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_NAME): cv.string,
    vol.Optional(ATTR_MEDIA_ID): cv.string,
    vol.Optional(ATTR_SEASON, default="latest"): cv.string
})

UPDATE_REQUEST_SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ID): cv.string,
    vol.Required(ATTR_STATUS): cv.string
})

SEARCH_SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_NAME): cv.string
})

def setup(hass, config):
    """Set up the Overseerr component."""
    conf = config[DOMAIN]
    api_key = conf.get(CONF_API_KEY)
    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)
    ssl = conf.get(CONF_SSL)
    urlbase = conf.get(CONF_URLBASE)
    
    # Optional password and username
    password = conf.get(CONF_PASSWORD)
    username = conf.get(CONF_USERNAME)

    overseerr = Overseerr(
        ssl=ssl,
        host=host,
        port=port,
        urlbase=urlbase,
        api_key=api_key,
        username=username,
        password=password
    )

    hass.data[DOMAIN] = {"instance": overseerr}

    async def submit_movie_request(call):
        """Submit request for movie."""
        name = call.data.get(ATTR_NAME)
        media_id = call.data.get(ATTR_MEDIA_ID)
        
        def _request_movie():
            if media_id:
                overseerr.request_movie(media_id)
            elif name:
                movies = overseerr.search_movie(name)["results"]
                if movies:
                    movie = movies[0]
                    overseerr.request_movie(movie["id"])
                else:
                    _LOGGER.warning("No movie found for %s", name)
            else:
                _LOGGER.warning("No movie name or id provided")

        await hass.async_add_executor_job(_request_movie)

    async def submit_tv_request(call):
        """Submit request for TV show."""
        name = call.data.get(ATTR_NAME)
        media_id = call.data.get(ATTR_MEDIA_ID)
        season = call.data[ATTR_SEASON]

        def _request_tv():
            start_id = None
            if media_id:
                start_id = media_id
            elif name:
                tv_shows = overseerr.search_tv(name)["results"]
                if tv_shows:
                    start_id = tv_shows[0]["id"]
                else:
                    _LOGGER.warning("No TV show found for %s", name)
            
            if start_id:
                if season == "first":
                    overseerr.request_tv(start_id, request_first=True)
                elif season == "latest":
                    overseerr.request_tv(start_id, request_latest=True)
                elif season == "all":
                    overseerr.request_tv(start_id, request_all=True)
            else:
                 _LOGGER.warning("No TV show identifier provided")

        await hass.async_add_executor_job(_request_tv)

    async def update_request(call):
        """Update status of specified request."""
        request_id = call.data[ATTR_ID]
        status = call.data[ATTR_STATUS]
        
        await hass.async_add_executor_job(overseerr.update_request, request_id, status)
    
    async def search_movie(call: ServiceCall) -> ServiceResponse:
        """Search for movies and return results."""
        name = call.data[ATTR_NAME]
        
        def _search_movie():
            return overseerr.search_movie(name)

        return await hass.async_add_executor_job(_search_movie)

    async def search_tv(call: ServiceCall) -> ServiceResponse:
        """Search for TV shows and return results."""
        name = call.data[ATTR_NAME]
        
        def _search_tv():
            return overseerr.search_tv(name)

        return await hass.async_add_executor_job(_search_tv)

    async def search_all(call: ServiceCall) -> ServiceResponse:
        """Search for both movies and TV shows and return combined results."""
        name = call.data[ATTR_NAME]
        
        def _search_all():
            try:
                movies = overseerr.search_movie(name).get("results", [])
                tv_shows = overseerr.search_tv(name).get("results", [])
                
                # Combine results
                combined = movies + tv_shows
                
                # Sort by popularity descending (handle missing popularity key safely)
                combined.sort(key=lambda x: x.get("popularity", 0), reverse=True)
                
                return {"results": combined}
            except Exception as e:
                _LOGGER.error("Error during unified search: %s", e)
                return {"results": []}

        return await hass.async_add_executor_job(_search_all)

    async def update_sensors(event_time):
        """Call to update sensors."""
        _LOGGER.debug("Updating sensors")
        await hass.services.async_call("homeassistant", "update_entity", {ATTR_ENTITY_ID: ["sensor.overseerr_pending_requests"]}, blocking=True)
        await hass.services.async_call("homeassistant", "update_entity", {ATTR_ENTITY_ID: ["sensor.overseerr_movie_requests"]}, blocking=True)
        await hass.services.async_call("homeassistant", "update_entity", {ATTR_ENTITY_ID: ["sensor.overseerr_tv_requests"]}, blocking=True)
        await hass.services.async_call("homeassistant", "update_entity", {ATTR_ENTITY_ID: ["sensor.overseerr_total_requests"]}, blocking=True)

    hass.services.register(DOMAIN, SERVICE_MOVIE_REQUEST, submit_movie_request, schema=SUBMIT_MOVIE_REQUEST_SERVICE_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_TV_REQUEST, submit_tv_request, schema=SUBMIT_TV_REQUEST_SERVICE_SCHEMA)
    hass.services.register(DOMAIN, "update_request", update_request, schema=UPDATE_REQUEST_SERVICE_SCHEMA)
    
    # Search Services
    hass.services.register(DOMAIN, SERVICE_SEARCH_MOVIE, search_movie, schema=SEARCH_SERVICE_SCHEMA, supports_response=SupportsResponse.ONLY)
    hass.services.register(DOMAIN, SERVICE_SEARCH_TV, search_tv, schema=SEARCH_SERVICE_SCHEMA, supports_response=SupportsResponse.ONLY)
    hass.services.register(DOMAIN, SERVICE_SEARCH, search_all, schema=SEARCH_SERVICE_SCHEMA, supports_response=SupportsResponse.ONLY)

    # Note: We removed the manual track_time_interval here. 
    # Sensors will rely on HA standard polling (if should_poll is True) or Webhooks.

    # Register Sensor
    load_platform(hass, "sensor", DOMAIN, {}, config)
    
    # Webhook support
    async def handle_webhook(hass, webhook_id, request):
        """Handle webhook callback."""
        try:
            data = await request.json()
        except ValueError:
            return None

        _LOGGER.debug("Webhook received: %s", data)
        # Process webhook data here to auto-update sensors
        # For now, just trigger an update
        await update_sensors(None)

    webhook_id = webhook.async_generate_id()
    webhook.async_register(hass, DOMAIN, "Overseerr", webhook_id, handle_webhook)
    
    _LOGGER.info("Overseerr integration setup complete")

    return True
