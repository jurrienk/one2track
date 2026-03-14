#!/bin/sh
REPO="jurrienk/one2track"
BETA_DIR="/config/custom_components/one2track_beta"

echo "Fetching available versions from GitHub..."
echo ""

echo "=== Releases ==="
RELEASES=$(curl -s "https://api.github.com/repos/${REPO}/releases" | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p')
if [ -z "$RELEASES" ]; then
    echo "  (none found)"
else
    echo "$RELEASES" | cat -n
fi

echo ""
echo "=== Branches ==="
BRANCHES=$(curl -s "https://api.github.com/repos/${REPO}/branches" | sed -n 's/.*"name": *"\([^"]*\)".*/\1/p')
if [ -z "$BRANCHES" ]; then
    echo "  (none found)"
else
    echo "$BRANCHES" | cat -n
fi

echo ""
printf "Enter a release tag or branch name: "
read VERSION

if [ -z "$VERSION" ]; then
    echo "No version specified, aborting."
    exit 1
fi

TAG_URL="https://github.com/${REPO}/archive/refs/tags/${VERSION}.zip"
BRANCH_URL="https://github.com/${REPO}/archive/refs/heads/${VERSION}.zip"

echo ""
echo "Trying to download ${VERSION}..."
cd /tmp
rm -f one2track-beta.zip
rm -rf one2track-beta-extract

if curl -fsSL -o one2track-beta.zip "$TAG_URL" 2>/dev/null; then
    echo "Downloaded release tag: ${VERSION}"
elif curl -fsSL -o one2track-beta.zip "$BRANCH_URL" 2>/dev/null; then
    echo "Downloaded branch: ${VERSION}"
else
    echo "ERROR: Could not download ${VERSION}"
    exit 1
fi

mkdir -p one2track-beta-extract
unzip -qo one2track-beta.zip -d one2track-beta-extract

EXTRACTED=$(find one2track-beta-extract -maxdepth 1 -mindepth 1 -type d | head -1)
if [ -z "$EXTRACTED" ] || [ ! -d "$EXTRACTED/custom_components/one2track" ]; then
    echo "ERROR: Unexpected archive structure."
    exit 1
fi

if [ -d "$BETA_DIR" ]; then
    echo "Removing previous beta installation..."
    rm -rf "$BETA_DIR"
fi

mkdir -p "$BETA_DIR"
cp -r "$EXTRACTED/custom_components/one2track/"* "$BETA_DIR/"

echo "Patching domain to one2track_beta..."

# manifest.json
sed -i 's/"domain": "one2track"/"domain": "one2track_beta"/g' "$BETA_DIR/manifest.json"
sed -i 's/"name": "One2Track"/"name": "One2Track Beta"/g' "$BETA_DIR/manifest.json"

# Domain constant (v4+ uses const.py, older versions used common.py)
if [ -f "$BETA_DIR/const.py" ]; then
    sed -i 's/DOMAIN = "one2track"/DOMAIN = "one2track_beta"/g' "$BETA_DIR/const.py"
fi
if [ -f "$BETA_DIR/common.py" ]; then
    sed -i 's/DOMAIN = "one2track"/DOMAIN = "one2track_beta"/g' "$BETA_DIR/common.py"
fi

# services.yaml
sed -i 's/integration: one2track$/integration: one2track_beta/g' "$BETA_DIR/services.yaml"

# strings.json and translations
sed -i 's/integration: one2track/integration: one2track_beta/g' "$BETA_DIR/strings.json"
if [ -d "$BETA_DIR/translations" ]; then
    for f in "$BETA_DIR/translations/"*.json; do
        [ -f "$f" ] && sed -i 's/integration: one2track/integration: one2track_beta/g' "$f"
    done
fi

# config_flow.py — patch the domain= argument
if [ -f "$BETA_DIR/config_flow.py" ]; then
    sed -i 's/domain=DOMAIN/domain="one2track_beta"/g' "$BETA_DIR/config_flow.py"
fi

rm -f /tmp/one2track-beta.zip
rm -rf /tmp/one2track-beta-extract

echo ""
echo "=== Installed One2Track Beta (${VERSION}) ==="
echo "Location: ${BETA_DIR}"
echo ""
printf "Restart Home Assistant now? [y/N]: "
read RESTART
if [ "$RESTART" = "y" ] || [ "$RESTART" = "Y" ]; then
    ha core restart
    echo "Restarting..."
else
    echo "Remember to restart HA manually."
fi
