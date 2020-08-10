IMAGE_NAME := $(subst _,-,$(shell (cd ..; python setup.py --name)))
VERSION := $(or ${VERSION},${VERSION},$(shell cat ../VERSION))

all:
	docker build --no-cache --tag $(IMAGE_NAME):$(VERSION) .