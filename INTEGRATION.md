# Dashboard Integration Guide

This guide allows you to build a **Search & Request** interface directly on your Home Assistant Dashboard using the new services.

## Overview
We will create:
1.  **Helpers**: To store query and pagination offset.
2.  **Sensor**: To store the detailed rich data.
3.  **Scripts**: To perform search, pagination, and cleanup.
4.  **Dashboard Card**: The UI with unified search and "Show More" functionality.

## 1. Create Helpers
You can create these in **Settings > Devices & Services > Helpers** or via YAML.

*   **Text Input**: `input_text.overseerr_search_query`
    *   Name: Overseerr Search
    *   Icon: mdi:magnify
*   **Number**: `input_number.overseerr_page_offset`
    *   Name: Overseerr Page Offset
    *   Minimum: 0
    *   Maximum: 100
    *   Step: 6
    *   Mode: Box

## 2. Configuration (YAML)
Add this to your `configuration.yaml` to create a sensor that can hold the rich result data.

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

### Script 1: Unified Search
**Entity ID**: `script.overseerr_search_logic`
Resets offset and performs unified search.

```yaml
alias: Overseerr - Unified Search Logic
sequence:
  # Reset Offset to 0
  - service: input_number.set_value
    target:
      entity_id: input_number.overseerr_page_offset
    data:
      value: 0
  # Call Unified Search Service
  - service: overseerr.search
    data:
      name: "{{ states('input_text.overseerr_search_query') }}"
    response_variable: search_data
  # Fire event to update the Rich Data Sensor
  - event: overseerr_search_complete
    event_data:
      results: "{{ search_data.results }}"
```

### Script 2: Show More (Pagination)
**Entity ID**: `script.overseerr_show_more`
Increments the offset to show the next batch of results.

```yaml
alias: Overseerr - Show More Results
sequence:
  - service: input_number.set_value
    target:
      entity_id: input_number.overseerr_page_offset
    data:
      value: "{{ states('input_number.overseerr_page_offset') | int + 6 }}"
```

### Script 3: Clear Search UI
**Entity ID**: `script.overseerr_clear_search`
Resets everything.

```yaml
alias: Overseerr - Clear Search
sequence:
  - service: input_text.set_value
    target:
      entity_id: input_text.overseerr_search_query
    data:
      value: ""
  - service: input_number.set_value
    target:
      entity_id: input_number.overseerr_page_offset
    data:
      value: 0
  - event: overseerr_search_complete
    event_data:
      results: []
```

### Script 4: Smart Request Wrapper (Auto-Clears)
**Entity ID**: `script.overseerr_request_smart_wrapper`

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
  
  # AUTO CLEAR UI AFTER REQUEST
  - delay: "00:00:02"
  - service: script.overseerr_clear_search
```

## 4. Dashboard Card

This configuration features:
*   Unified **"Search"** button.
*   **"Show More"** button below results.
*   Results with **TYPE TAGS** (Movie/TV).

```yaml
type: vertical-stack
cards:
  # --- ROW 1: SEARCH BAR & CLEAR BUTTON ---
  - type: horizontal-stack
    cards:
      - type: entities
        show_header_toggle: false
        entities:
          - entity: input_text.overseerr_search_query
            name: Search Query
      
      - type: button
        icon: mdi:close
        tap_action:
          action: call-service
          service: script.overseerr_clear_search
  
  # --- ROW 2: UNIFIED SEARCH BUTTON ---
  - type: button
    name: Search
    icon: mdi:magnify
    tap_action:
      action: call-service
      service: script.overseerr_search_logic

  # --- ROW 3: PAGINATED RESULTS GRID ---
  - type: custom:auto-entities
    card:
      type: grid
      columns: 2
      square: false
    card_param: cards
    filter:
      template: |
        {% set results = state_attr('sensor.overseerr_search_json', 'results') %}
        {% set offset = states('input_number.overseerr_page_offset') | int %}
        {% set ns = namespace(cards=[]) %}
        
        {% if results %}
          {# SLICE RESULTS BASED ON OFFSET (Show 6 items) #}
          {% for item in results[offset : offset+6] %}
            {# SAFELY GET DATA #}
            {% set title = item.get('title') or item.get('name') or 'Unknown' %}
            {% set date_full = item.get('releaseDate') or item.get('firstAirDate') %}
            {% set date_full = date_full | string | default('') %}
            {% set year = date_full[:4] if date_full else 'N/A' %}
            {% set poster_path = item.get('posterPath') %}
            {% set poster = "https://image.tmdb.org/t/p/w300" ~ poster_path if poster_path else "https://via.placeholder.com/300x450?text=No+Image" %}
            {% set media_id = item.get('id') %}
            {% set media_type = item.get('mediaType', 'movie') %}
            {% set type_label = "TV" if media_type == 'tv' else "MOVIE" %}
            {% set type_color = "rgba(40, 167, 69, 0.9)" if media_type == 'tv' else "rgba(0, 123, 255, 0.9)" %}

            {# CREATE CARD CONFIGURATION OBJECT #}
            {% set card_config = {
              "type": "custom:button-card",
              "aspect_ratio": "1",
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
                ],
                "custom_fields": {
                   "type_tag": [
                      "position: absolute",
                      "top: 5px",
                      "right: 5px",
                      "background-color: " ~ type_color,
                      "color: white",
                      "padding: 2px 6px",
                      "border-radius: 4px",
                      "font-size: 10px",
                      "font-weight: bold",
                      "text-transform: uppercase"
                   ]
                }
              },
              "custom_fields": {
                 "type_tag": type_label
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

  # --- ROW 4: SHOW MORE BUTTON (Conditional) ---
  - type: conditional
    conditions:
      - condition: template
        value_template: >
          {% set results = state_attr('sensor.overseerr_search_json', 'results') %}
          {% set offset = states('input_number.overseerr_page_offset') | int %}
          {{ results and (results | length) > (offset + 6) }}
    card:
      type: button
      name: Show Next 6
      icon: mdi:arrow-down-bold
      tap_action:
        action: call-service
        service: script.overseerr_show_more
```
