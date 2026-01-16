# Test Output Directory

This directory is used for storing test artifacts and output files during testing.

## Structure

- `progress/` - Test progress files (mapping_progress.json)
- `mappings/` - Test mapping files (mappings.json)
- `categories/` - Test category files (categories.json)

## Usage

When running tests, you can configure the application to use this directory by setting environment variables or modifying the test fixtures in `backend/tests/conftest.py`.

## Cleanup

All files in this directory (except `.gitkeep` files) are ignored by git. You can safely delete the contents of this directory at any time.

