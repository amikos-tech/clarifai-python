import os
import time
import typing

import pytest

from clarifai.client.search import Search
from clarifai.client.user import User
from clarifai.errors import UserError

CREATE_APP_USER_ID = os.environ["CLARIFAI_USER_ID"]
now = int(time.time())
CREATE_APP_ID = f"ci_search_app_{now}"
DOG_IMG_URL = "https://samples.clarifai.com/dog.tiff"


def get_filters_for_test() -> [(typing.List[typing.Dict], int)]:
  return [
      ([{
          "geo_point": {
              "longitude": -29.0,
              "latitude": 40.0,
              "geo_limit": 10
          }
      }], 1),
      ([{
          "concepts": [{
              "name": "dog",
              "value": 1
          }]
      }], 1),
      (
          [{  # OR
              "concepts": [{
                  "name": "deer",
                  "value": 1
              }, {
                  "name": "dog",
                  "value": 1
              }]
          }],
          1),
      (
          [
              {  # AND
                  "concepts": [{
                      "name": "dog",
                      "value": 1
                  }]
              },
              {
                  "concepts": [{
                      "name": "deer",
                      "value": 1
                  }]
              }
          ],
          0)
  ]


class TestAnnotationSearch:

  @classmethod
  def setup_class(cls):
    cls.client = User(user_id=CREATE_APP_USER_ID)
    cls.search = Search(
        user_id=CREATE_APP_USER_ID, app_id=CREATE_APP_ID, top_k=1, metric="euclidean")
    cls.upload_input()

  @classmethod
  def upload_input(self):
    inp_obj = self.client.create_app(CREATE_APP_ID, base_workflow="General").inputs()
    input_proto = inp_obj.get_input_from_url(
        input_id="dog-tiff",
        image_url=DOG_IMG_URL,
        labels=["dog"],
        geo_info=[-30.0, 40.0]  # longitude, latitude
    )
    inp_obj.upload_inputs([input_proto])

  @pytest.mark.parametrize("filter_dict_list,expected_hits", get_filters_for_test())
  def test_filter_search(self, filter_dict_list: typing.List[typing.Dict], expected_hits: int):
    query = self.search.query(filters=filter_dict_list)
    for q in query:
      assert len(q.hits) == expected_hits
      if expected_hits:
        assert q.hits[0].input.id == "dog-tiff"

  def test_rank_search(self):
    query = self.search.query(ranks=[{"image_url": "https://samples.clarifai.com/dog.tiff"}])
    for q in query:
      assert len(q.hits) == 1
      assert q.hits[0].input.id == "dog-tiff"

  def test_schema_error(self):
    with pytest.raises(UserError):
      _ = self.search.query(filters=[{
          "geo_point": {
              "longitude": -29.0,
              "latitude": 40.0,
              "geo_limit": 10,
              "extra": 1
          }
      }])

    # Incorrect Concept Keys
    with pytest.raises(UserError):
      _ = self.search.query(filters=[{
          "concepts": [{
              "value": 1,
              "concept_id": "deer"
          }, {
              "name": "dog",
              "value": 1
          }]
      }])

    # Incorrect Concept Values
    with pytest.raises(UserError):
      _ = self.search.query(filters=[{
          "concepts": [{
              "name": "deer",
              "value": 2
          }, {
              "name": "dog",
              "value": 1
          }]
      }])

  def teardown_class(cls):
    cls.client.delete_app(app_id=CREATE_APP_ID)
