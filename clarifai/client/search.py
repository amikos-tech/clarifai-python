from typing import Any, Callable, Dict, Generator

from clarifai_grpc.grpc.api import resources_pb2, service_pb2
from clarifai_grpc.grpc.api.status import status_code_pb2
from google.protobuf.json_format import MessageToDict
from google.protobuf.struct_pb2 import Struct
from schema import SchemaError

from clarifai.client.base import BaseClient
from clarifai.client.input import Inputs
from clarifai.client.lister import Lister
from clarifai.constants.search import DEFAULT_SEARCH_METRIC, DEFAULT_TOP_K
from clarifai.errors import UserError
from clarifai.schema.search import get_schema


class Search(Lister, BaseClient):

  def __init__(self,
               user_id,
               app_id,
               top_k: int = DEFAULT_TOP_K,
               metric: str = DEFAULT_SEARCH_METRIC):
    """Initialize the Search object.

        Args:
            user_id (str): User ID.
            app_id (str): App ID.
            top_k (int, optional): Top K results to retrieve. Defaults to 10.
            metric (str, optional): Similarity metric (either 'cosine' or 'euclidean'). Defaults to 'cosine'.

        Raises:
            UserError: If the metric is not 'cosine' or 'euclidean'.
        """
    if metric not in ["cosine", "euclidean"]:
      raise UserError("Metric should be either cosine or euclidean")

    self.user_id = user_id
    self.app_id = app_id
    self.metric_distance = dict(cosine="COSINE_DISTANCE", euclidean="EUCLIDEAN_DISTANCE")[metric]
    self.data_proto = resources_pb2.Data()

    self.inputs = Inputs(user_id=self.user_id, app_id=self.app_id)
    self.rank_filter_schema = get_schema()
    BaseClient.__init__(self, user_id=self.user_id, app_id=self.app_id)
    Lister.__init__(self, page_size=top_k)

  def _get_annot_proto(self, **kwargs):
    """Get an Annotation proto message based on keyword arguments.

        Args:
            **kwargs: Keyword arguments specifying the resource.

        Returns:
            resources_pb2.Annotation: An Annotation proto message.
        """
    if not kwargs:
      return resources_pb2.Annotation()

    self.data_proto = resources_pb2.Data()
    for key, value in kwargs.items():
      if key == "image_bytes":
        image_proto = self.inputs.get_input_from_bytes("", image_bytes=value).data.image
        self.data_proto.image.CopyFrom(image_proto)

      elif key == "image_url":
        image_proto = self.inputs.get_input_from_url("", image_url=value).data.image
        self.data_proto.image.CopyFrom(image_proto)

      elif key == "concepts":
        for concept in value:
          concept_proto = resources_pb2.Concept(**concept)
          self.data_proto.concepts.add().CopyFrom(concept_proto)

      elif key == "text_raw":
        text_proto = self.inputs.get_input_from_bytes(
            "", text_bytes=bytes(value, 'utf-8')).data.text
        self.data_proto.text.CopyFrom(text_proto)

      elif key == "metadata":
        metadata_struct = Struct()
        metadata_struct.update(value)
        self.data_proto.metadata.CopyFrom(metadata_struct)

      elif key == "geo_point":
        geo_point_proto = self._get_geo_point_proto(value["longitude"], value["latitude"],
                                                    value["geo_limit"])
        self.data_proto.geo.CopyFrom(geo_point_proto)

      else:
        raise UserError(f"kwargs contain key that is not supported: {key}")
    return resources_pb2.Annotation(data=self.data_proto)

  def _get_geo_point_proto(self, longitude: float, latitude: float,
                           geo_limit: float) -> resources_pb2.Geo:
    """Get a GeoPoint proto message based on geographical data.

        Args:
            longitude (float): Longitude coordinate.
            latitude (float): Latitude coordinate.
            geo_limit (float): Geographical limit.

        Returns:
            resources_pb2.Geo: A Geo proto message.
        """
    return resources_pb2.Geo(
        geo_point=resources_pb2.GeoPoint(longitude=longitude, latitude=latitude),
        geo_limit=resources_pb2.GeoLimit(type="withinKilometers", value=geo_limit))

  def list_all_pages_generator(
      self, endpoint: Callable[..., Any], proto_message: Any,
      request_data: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
    """Lists all pages of a resource.

        Args:
            endpoint (Callable): The endpoint to call.
            proto_message (Any): The proto message to use.
            request_data (dict): The request data to use.

        Yields:
            response_dict: The next item in the listing.
        """
    page = 1
    request_data['pagination'] = service_pb2.Pagination(page=page, per_page=self.default_page_size)
    while True:
      request_data['pagination'].page = page
      response = self._grpc_request(endpoint, proto_message(**request_data))
      dict_response = MessageToDict(response, preserving_proto_field_name=True)
      if response.status.code != status_code_pb2.SUCCESS:
        raise Exception(f"Listing failed with response {response!r}")

      if 'hits' not in list(dict_response.keys()):
        break
      page += 1
      yield response

  def query(self, ranks=[{}], filters=[{}]):
    """Perform a query with rank and filters.

        Args:
            ranks (List[Dict], optional): List of rank parameters. Defaults to [{}].
            filters (List[Dict], optional): List of filter parameters. Defaults to [{}].

        Returns:
            Generator[Dict[str, Any], None, None]: A generator of query results.
        """
    try:
      self.rank_filter_schema.validate(ranks)
      self.rank_filter_schema.validate(filters)
    except SchemaError as err:
      raise UserError(f"Invalid rank or filter input: {err}")

    rank_annot_proto, filters_annot_proto = [], []
    for rank_dict in ranks:
      rank_annot_proto.append(self._get_annot_proto(**rank_dict))
    for filter_dict in filters:
      filters_annot_proto.append(self._get_annot_proto(**filter_dict))

    all_ranks = [resources_pb2.Rank(annotation=rank_annot) for rank_annot in rank_annot_proto]
    all_filters = [
        resources_pb2.Filter(annotation=filter_annot) for filter_annot in filters_annot_proto
    ]

    request_data = dict(
        user_app_id=self.user_app_id,
        searches=[
            resources_pb2.Search(
                query=resources_pb2.Query(ranks=all_ranks, filters=all_filters),
                metric=self.metric_distance)
        ])

    return self.list_all_pages_generator(self.STUB.PostAnnotationsSearches,
                                         service_pb2.PostAnnotationsSearchesRequest, request_data)
