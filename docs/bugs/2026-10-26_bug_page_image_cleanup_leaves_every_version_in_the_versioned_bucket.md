# Bug name: The page-image cleanup leaves every image in the versioned statement bucket

## Problem

The one-time script for DP-ING-11 is meant to remove the page images that earlier Tier 2 runs left next to
statement files. Run against the statement bucket, it reported success and deleted nothing that mattered:
every image was still stored, and bank-statement copies stayed in the bucket after the account that owned
them was deleted.

### Root cause

The bucket is versioned. `delete_objects` without a `VersionId` only adds a delete marker; every earlier
version stays. The script also listed current objects only, so it never saw versions or delete markers, and it
removed an image only if the statement's original file was still in the bucket, which skipped exactly the
images whose originals had already been deleted.

### Code with bug

`services/fintracker-data-pipeline/scripts/one-time/2026-10-25_DP-ING-11_remove_textract_page_images.py`

```python
found = find_page_images(_all_keys(s3, bucket))          # list_objects_v2: current objects only
...
s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True})
```

## Solution

List every version and delete marker with `list_object_versions`, match the page-image key shape, and delete
each `(Key, VersionId)` pair in batches of 1,000. The "original must still exist" condition is gone: an image
whose original was deleted is the copy deletion missed. A user's own upload directly under a statement prefix
still never matches, because page images sit one folder deeper. The tests run against a versioned moto bucket
and check `list_object_versions` afterwards, which is where the old script's result would have shown.

### Fixed Code

```python
def _all_versions(s3, bucket):
    entries = []
    for page in s3.get_paginator("list_object_versions").paginate(Bucket=bucket, Prefix="statements/"):
        for item in [*page.get("Versions", []), *page.get("DeleteMarkers", [])]:
            entries.append({"Key": item["Key"], "VersionId": item["VersionId"]})
    return entries

...
s3.delete_objects(Bucket=bucket, Delete={"Objects": batch, "Quiet": True})
```
