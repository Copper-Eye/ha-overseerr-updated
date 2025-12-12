# Dashboard Integration Guide

This guide allows you to build a **Search & Request** interface directly on your Home Assistant Dashboard using the new services.

## Overview
We will create:
1.  **Helpers**: To store your search query and the list of results.
2.  **Sensor**: To store the detailed rich data (images, overview).
3.  **Scripts**: To perform the search and populate the data.
4.  **Dashboard Card**: The UI to interact with these scripts and view results.

## 1. Create Helpers
You can create these in **Settings > Devices & Services > Helpers** or via YAML.

*   **Text Input**: `input_text.overseerr_search_query`
    *   Name: Overseerr Search
    *   Icon: mdi:magnify
*   **Dropdown (Input Select)**: `input_select.overseerr_search_results`
    *   Name: Overseerr Results
    *   Options: (Add a dummy option like "No results")
*   **Toggle (Boolean)**: `input_boolean.overseerr_is_tv`
    *   Name: Search for TV Shows?
    *   Icon: mdi:television-classic

## 2. Configuration (YAML)
Add this to your `configuration.yaml` to create a sensor that can hold the rich result data (images, descriptions) which scripts cannot store easily.

```yaml
template:
  - trigger:
      - platform: event
        event_type: overseerr_search_complete
    sensor:
      - name: Overseerr Search JSON
        unique_id: overseerr_search_json
        state: "OK"
        attributes:
          results: "{{ trigger.event.data.results }}"
```
*Note: You must restart Home Assistant after adding this.*

## 3. Create Scripts
Add these to your `scripts.yaml`.

### Script 1: Search Movies
**Entity ID**: `script.overseerr_search_movie_logic`

```yaml
alias: Overseerr - Search Movie Logic
sequence:
  - service: overseerr.search_movies
    data:
      name: "{{ states('input_text.overseerr_search_query') }}"
    response_variable: search_data
  # Fire event to update the Rich Data Sensor
  - event: overseerr_search_complete
    event_data:
      results: "{{ search_data.results }}"
  # Populate the Dropdown for selection (Optional if using visual grid)
  - service: input_select.set_options
    target:
      entity_id: input_select.overseerr_search_results
    data:
      options: >
        {% set RESULTS = search_data.results %}
        {% if RESULTS | length == 0 %}
          {{ ['No Results Found'] }}
        {% else %}
          {% set ns = namespace(options=[]) %}
          {% for item in RESULTS %}
             {% set year = item.releaseDate[:4] if item.releaseDate else 'N/A' %}
             {# Format: "Title (Year) [ID:123]" #}
             {% set option = item.title ~ " (" ~ year ~ ") [ID:" ~ item.id ~ "]" %}
             {% set ns.options = ns.options + [option] %}
          {% endfor %}
          {{ ns.options }}
        {% endif %}
  - service: input_select.select_first
    target:
      entity_id: input_select.overseerr_search_results
```

### Script 2: Search TV
**Entity ID**: `script.overseerr_search_tv_logic`

```yaml
alias: Overseerr - Search TV Logic
sequence:
  - service: overseerr.search_tv
    data:
      name: "{{ states('input_text.overseerr_search_query') }}"
    response_variable: search_data
  # Fire event to update the Rich Data Sensor
  - event: overseerr_search_complete
    event_data:
      results: "{{ search_data.results }}"
  # Populate the Dropdown for selection
  - service: input_select.set_options
    target:
      entity_id: input_select.overseerr_search_results
    data:
      options: >
        {% set RESULTS = search_data.results %}
        {% if RESULTS | length == 0 %}
          {{ ['No Results Found'] }}
        {% else %}
          {% set ns = namespace(options=[]) %}
          {% for item in RESULTS %}
             {% set year = item.firstAirDate[:4] if item.firstAirDate else 'N/A' %}
             {# Format: "Name (Year) [ID:123]" #}
             {% set option = item.name ~ " (" ~ year ~ ") [ID:" ~ item.id ~ "]" %}
             {% set ns.options = ns.options + [option] %}
          {% endfor %}
          {{ ns.options }}
        {% endif %}
  - service: input_select.select_first
    target:
      entity_id: input_select.overseerr_search_results
```

### Script 3: Smart Request Wrapper
**Entity ID**: `script.overseerr_request_smart_wrapper`
This script handles the request from the visual cards, detecting if it's a Movie or TV show.

```yaml
alias: Overseerr - Smart Request Wrapper
fields:
  media_id:
    description: TMDB ID
    example: 123
  media_type:
    description: movie or tv
    example: movie
sequence:
  - if:
      - condition: template
        value_template: "{{ media_type == 'tv' }}"
    then:
      - service: overseerr.submit_tv_request
        data:
          media_id: "{{ media_id | int }}"
    else:
      - service: overseerr.submit_movie_request
        data:
          media_id: "{{ media_id | int }}"
  - service: notify.persistent_notification
    data:
      message: "Request sent for ID: {{ media_id }}"
```

### Script 4: Request Selected (Dropdown Fallback)
**Entity ID**: `script.overseerr_submit_selection`

```yaml
alias: Overseerr - Submit Selection
sequence:
  - variables:
      selected_option: "{{ states('input_select.overseerr_search_results') }}"
  - if:
      - condition: template
        value_template: "{{ '[ID:' in selected_option }}"
    then:
      - variables:
          media_id: "{{ selected_option.split('[ID:')[1][:-1] | int }}"
      - if:
          - condition: state
            entity_id: input_boolean.overseerr_is_tv 
            state: "on"
        then:
          - service: overseerr.submit_tv_request
            data:
              media_id: "{{ media_id }}"
        else:
          - service: overseerr.submit_movie_request
            data:
              media_id: "{{ media_id }}"
      - service: notify.persistent_notification
        data:
          message: "Request sent for {{ selected_option }}"
```

## 4. Advanced Dashboard (Custom Cards)

This configuration uses `auto-entities` and `button-card` (install via HACS) to create a **Visual Grid of Posters**. Clicking a poster sends the request immediately.

```yaml
type: vertical-stack
cards:
  # --- SEARCH SECTION ---
  - type: entities
    show_header_toggle: false
    entities:
      - entity: input_text.overseerr_search_query
        name: Search Query
      - entity: input_boolean.overseerr_is_tv
        name: Search for TV Shows?
  
  - type: horizontal-stack
    cards:
      - type: conditional
        conditions:
          - entity: input_boolean.overseerr_is_tv
            state: "off"
        card:
          type: button
          name: Search Movies
          icon: mdi:movie-search
          tap_action:
            action: call-service
            service: script.overseerr_search_movie_logic
      - type: conditional
        conditions:
          - entity: input_boolean.overseerr_is_tv
            state: "on"
        card:
          type: button
          name: Search TV Shows
          icon: mdi:television-classic
          tap_action:
            action: call-service
            service: script.overseerr_search_tv_logic

  # --- ADVANCED VISUAL GRID ---
  - type: custom:auto-entities
    card:
      type: grid
      columns: 3
      square: false
    card_param: cards
    filter:
      template: |
        {% set results = state_attr('sensor.overseerr_search_json', 'results') %}
        {% set ns = namespace(cards=[]) %}
        {% if results %}
          {# LIMIT TO TOP 5 RESULTS #}
          {% for item in results[:5] %}
            {# SAFELY GET DATA #}
            {% set title = item.get('title') or item.get('name') or 'Unknown' %}
            {% set date_full = item.get('releaseDate') or item.get('firstAirDate') %}
            {% set date_full = date_full | string | default('') %}
            {% set year = date_full[:4] if date_full else 'N/A' %}
            {% set poster_path = item.get('posterPath') %}
            {% set poster = "https://image.tmdb.org/t/p/w300" ~ poster_path if poster_path else "https://via.placeholder.com/300x450?text=No+Image" %}
            {% set media_id = item.get('id') %}
            {% set media_type = item.get('mediaType', 'movie') %}

            {# CREATE CARD CONFIGURATION OBJECT #}
            {% set card_config = {
              "type": "custom:button-card",
              "aspect_ratio": "2/3",
              "entity": "sensor.overseerr_search_json",
              "name": title ~ " (" ~ year ~ ")",
              "show_entity_picture": true,
              "entity_picture": poster,
              "styles": {
                "card": [
                  "padding: 0px",
                  "border-radius: 12px",
                  "overflow: hidden"
                ],
                "img_cell": [
                  "justify-content: center",
                  "align-items: center"
                ],
                "entity_picture": [
                  "width: 100%",
                  "height: 100%",
                  "object-fit: cover"
                ],
                "name": [
                  "position: absolute",
                  "bottom: 0",
                  "left: 0",
                  "width: 100%",
                  "background: rgba(0, 0, 0, 0.7)",
                  "color: white",
                  "font-size: 12px",
                  "padding: 5px",
                  "font-weight: bold"
                ]
              },
              "tap_action": {
                "action": "call-service",
                "service": "script.overseerr_request_smart_wrapper",
                "service_data": {
                  "media_id": media_id,
                  "media_type": media_type
                }
              },
              "haptic": "success"
            } %}
            {% set ns.cards = ns.cards + [card_config] %}
          {% endfor %}
        {% endif %}
        {{ ns.cards }}
```
