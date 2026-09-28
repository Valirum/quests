# Bake definition for Quests images (Go API + Python bot + STT sidecar).
#
# Local:
#   docker buildx bake -f deploy/docker/docker-bake.hcl api
#   docker buildx bake -f deploy/docker/docker-bake.hcl api bot stt
#
# CI sets API_IMAGE / BOT_IMAGE / STT_IMAGE / TAG via --set / bake-action vars.

variable "API_IMAGE" {
  default = "quests-api:local"
}

variable "BOT_IMAGE" {
  default = "quests-bot:local"
}

variable "STT_IMAGE" {
  default = "quests-stt:local"
}

variable "TAG" {
  default = "local"
}

target "_common" {
  context    = "."
  dockerfile = "deploy/docker/Dockerfile"
  # Same scope so api+bot rebuilds reuse GHA cache for python-base.
  cache-from = ["type=gha,scope=quests"]
  cache-to   = ["type=gha,mode=max,scope=quests"]
}

target "api" {
  inherits = ["_common"]
  target   = "api"
  tags = [
    "${API_IMAGE}:main",
    "${API_IMAGE}:${TAG}",
  ]
}

target "bot" {
  inherits = ["_common"]
  target   = "bot"
  tags = [
    "${BOT_IMAGE}:main",
    "${BOT_IMAGE}:${TAG}",
  ]
}

target "stt" {
  inherits = ["_common"]
  target   = "stt"
  tags = [
    "${STT_IMAGE}:main",
    "${STT_IMAGE}:${TAG}",
  ]
}

group "default" {
  targets = ["api", "bot", "stt"]
}
