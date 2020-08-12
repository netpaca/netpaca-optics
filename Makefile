IMAGE_NAME := $(subst _,-,$(shell python setup.py --name))
VERSION := $(or ${VERSION},${VERSION},$(shell cat VERSION))

all:
	docker build --tag $(IMAGE_NAME):$(VERSION) .

force:
	docker build --no-cache --tag $(IMAGE_NAME):$(VERSION) .