Python's stdlib uuid.uuid4() already covers it — I just wired it in, no need for a custom generator. Added two flags:

--user-id <uuid>: pin a specific internal UUID
--generate-user-id: auto-generate one with uuid.uuid4()
Omit both → falls back to the existing shared DEV_USER_ID, so nothing breaks for your current dev user

To load both users into the persistent local table:

cd scripts
export DYNAMODB_ENDPOINT_URL=http://localhost:8000

# Existing dev user — unchanged, maps to the shared DEV_USER_ID
poetry run python dev_setup_user.py --sub <existing_dev_cognito_sub> --email dev@example.com

# New second user — gets its own fresh internal UUID
poetry run python dev_setup_user.py --sub <second_cognito_sub> --email second@example.com --generate-user-id
