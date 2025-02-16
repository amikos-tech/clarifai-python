from schema import And, Optional, Regex, Schema


def get_schema() -> Schema:
  """Initialize the schema for rank and filter.

        This schema validates:

        - Rank and filter must be a list
        - Each item in the list must be a dict
        - The dict can contain these optional keys:
            - 'image_url': Valid URL string
            - 'text_raw': Non-empty string
            - 'metadata': Dict
            - 'image_bytes': Bytes
            - 'geo_point': Dict with 'longitude', 'latitude' and 'geo_limit' as float, float and int respectively
            - 'concepts': List where each item is a concept dict
        - Concept dict requires at least one of:
            - 'name': Non-empty string with dashes/underscores
            - 'id': Non-empty string
            - 'language': Non-empty string
            - 'value': 0 or 1 integer

        Returns:
            Schema: The schema for rank and filter.
        """
  # Schema for a single concept
  concept_schema = Schema({
      Optional('value'):
          And(int, lambda x: x in [0, 1]),
      Optional('id'):
          And(str, len),
      Optional('language'):
          And(str, len),
      # Non-empty strings with internal dashes and underscores.
      Optional('name'):
          And(str, len, Regex(r'^[0-9A-Za-z]+([-_][0-9A-Za-z]+)*$'))
  })

  # Schema for a rank or filter item
  rank_filter_item_schema = Schema({
      Optional('image_url'):
          And(str, Regex(r'^https?://')),
      Optional('text_raw'):
          And(str, len),
      Optional('metadata'):
          dict,
      Optional('image_bytes'):
          bytes,
      Optional('geo_point'): {
          'longitude': float,
          'latitude': float,
          'geo_limit': int
      },
      Optional("concepts"):
          And(list, lambda x: all(concept_schema.is_valid(item) and len(item) > 0 for item in x)),
  })

  # Schema for rank and filter args
  return Schema([rank_filter_item_schema])
