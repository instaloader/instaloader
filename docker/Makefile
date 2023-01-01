INSTALOADER_NAME=instaloader

include build-inputs.mk
build:
	envsubst < Dockerfile.tpl > Dockerfile
	docker build --rm -t ${INSTALOADER_NAME}:${INSTALOADER_VERSION} .
	rm -v Dockerfile
