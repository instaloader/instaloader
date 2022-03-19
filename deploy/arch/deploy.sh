#!/usr/bin/env bash

VERSION=${1:1}

# do not deploy pre-releases
echo $VERSION | grep -qe "[abc]" && exit 0

cd $(dirname $0)

# decrypt and add ssh key
openssl aes-256-cbc -K $AUR_KEY -iv $AUR_IV -in id_rsa_AUR.enc -out /tmp/AUR_openssh -d
eval "$(ssh-agent -s)"
chmod 600 /tmp/AUR_openssh
ssh-add /tmp/AUR_openssh
mkdir -p ~/.ssh
ssh-keyscan -t rsa aur.archlinux.org >> ~/.ssh/known_hosts

# clone and modify AUR repo
git clone --depth 1 ssh://aur@aur.archlinux.org/instaloader.git

curl -sSfOJ https://codeload.github.com/instaloader/instaloader/tar.gz/$1
HASH=$(sha512sum instaloader-$VERSION.tar.gz | cut -f1 -d " ")
sed -e "s/{{version}}/$VERSION/g" -e "s/{{hash}}/$HASH/g" PKGBUILD.template > instaloader/PKGBUILD
sed -e "s/{{version}}/$VERSION/g" -e "s/{{hash}}/$HASH/g" .SRCINFO.template > instaloader/.SRCINFO

# commit and push changes
cd instaloader
git config user.email "koch-kramer@web.de"
git config user.name "André Koch-Kramer"
git add .
git commit -m "Release of version $VERSION"
git push
