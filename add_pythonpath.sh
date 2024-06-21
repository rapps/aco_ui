SCRIPTPATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"
echo adding $SCRIPTPATH to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:${SCRIPTPATH}"
python -c "import sys; print(sys.path)"

# Add current folder to PYTHONPATH
CURRENT_FOLDER=$(pwd)
SITE_PACKAGES_FOLDER="$(ls -d $(poetry env info -p)/lib/python*/site-packages/)project_dir.pth"
echo "$CURRENT_FOLDER" > "$SITE_PACKAGES_FOLDER"

python -c "import sys; print(sys.path)"