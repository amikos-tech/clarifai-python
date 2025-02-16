import os

import pytest
from clarifai_grpc.grpc.api import resources_pb2

from clarifai.client.model import Model
from clarifai.errors import UserError

DOG_IMAGE_URL = "https://samples.clarifai.com/dog2.jpeg"
NON_EXISTING_IMAGE_URL = "http://example.com/non-existing.jpg"
RED_TRUCK_IMAGE_FILE_PATH = os.path.dirname(__file__) + "/assets/red-truck.png"
BEER_VIDEO_URL = "https://samples.clarifai.com/beer.mp4"

MAIN_APP_ID = "main"
MAIN_APP_USER_ID = "clarifai"
GENERAL_MODEL_ID = "aaa03c23b3724a16a56b629203edc62c"
CLIP_EMBED_MODEL_ID = "multimodal-clip-embed"

RAW_TEXT = "Hi my name is Jim."
RAW_TEXT_BYTES = b"Hi my name is Jim."


@pytest.fixture
def model():
  return Model(user_id=MAIN_APP_USER_ID, app_id=MAIN_APP_ID, model_id=GENERAL_MODEL_ID)


def validate_concepts_length(response):
  assert len(response.outputs[0].data.concepts) > 0


def test_predict_image_url(model):
  response = model.predict_by_url(DOG_IMAGE_URL, input_type="image")
  validate_concepts_length(response)


def test_predict_filepath(model):
  response = model.predict_by_filepath(RED_TRUCK_IMAGE_FILE_PATH, input_type="image")
  validate_concepts_length(response)


def test_predict_image_bytes(model):
  with open(RED_TRUCK_IMAGE_FILE_PATH, "rb") as f:
    image_bytes = f.read()

  response = model.predict_by_bytes(image_bytes, input_type="image")
  validate_concepts_length(response)


def test_predict_image_url_with_selected_concepts():
  selected_concepts = [
      resources_pb2.Concept(name="dog"),
      resources_pb2.Concept(name="cat"),
  ]
  model_with_selected_concepts = Model(
      user_id=MAIN_APP_USER_ID,
      app_id=MAIN_APP_ID,
      model_id=GENERAL_MODEL_ID,
      output_config={
          "select_concepts": selected_concepts
      })

  response = model_with_selected_concepts.predict_by_url(DOG_IMAGE_URL, input_type="image")
  concepts = response.outputs[0].data.concepts

  assert len(concepts) == 2
  dog_concept = next(c for c in concepts if c.name == "dog")
  cat_concept = next(c for c in concepts if c.name == "cat")
  assert dog_concept.value > cat_concept.value


def test_predict_image_url_with_min_value():
  model_with_min_value = Model(
      user_id=MAIN_APP_USER_ID,
      app_id=MAIN_APP_ID,
      model_id=GENERAL_MODEL_ID,
      output_config={
          "min_value": 0.98
      })

  response = model_with_min_value.predict_by_url(DOG_IMAGE_URL, input_type="image")
  assert len(response.outputs[0].data.concepts) > 0
  for c in response.outputs[0].data.concepts:
    assert c.value >= 0.98


def test_predict_image_url_with_max_concepts():
  model_with_max_concepts = Model(
      user_id=MAIN_APP_USER_ID,
      app_id=MAIN_APP_ID,
      model_id=GENERAL_MODEL_ID,
      output_config={
          "max_concepts": 3
      })

  response = model_with_max_concepts.predict_by_url(DOG_IMAGE_URL, input_type="image")
  assert len(response.outputs[0].data.concepts) == 3


def test_failed_predicts(model):
  # Invalid FilePath
  false_filepath = "false_filepath"
  with pytest.raises(UserError):
    model.predict_by_filepath(false_filepath, input_type="image")

  # Invalid URL
  with pytest.raises(Exception):
    model.predict_by_url(NON_EXISTING_IMAGE_URL, input_type="image")


def test_predict_video_url_with_custom_sample_ms():
  model_with_custom_sample_ms = Model(
      user_id=MAIN_APP_USER_ID,
      app_id=MAIN_APP_ID,
      model_id=GENERAL_MODEL_ID,
      output_config={
          "sample_ms": 2000
      })

  response = model_with_custom_sample_ms.predict_by_url(BEER_VIDEO_URL, input_type="video")
  # The expected time per frame is the middle between the start and the end of the frame
  # (in milliseconds).
  expected_time = 1000

  assert len(response.outputs[0].data.frames) > 0
  for frame in response.outputs[0].data.frames:
    assert frame.frame_info.time == expected_time
    expected_time += 2000


def test_text_embed_predict_with_raw_text():
  clip_dim = 512
  clip_embed_model = Model(
      user_id=MAIN_APP_USER_ID, app_id=MAIN_APP_ID, model_id=CLIP_EMBED_MODEL_ID)

  response = clip_embed_model.predict_by_bytes(RAW_TEXT.encode(encoding='UTF-8'), "text")
  assert response.outputs[0].data.embeddings[0].num_dimensions == clip_dim

  response = clip_embed_model.predict_by_bytes(RAW_TEXT_BYTES, "text")
  assert response.outputs[0].data.embeddings[0].num_dimensions == clip_dim
