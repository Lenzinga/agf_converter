# AGF Converter

A Python tool to decrypt and convert `.agf` (AgData) field boundary files into standard ESRI Shapefiles (`.shp`), including WGS84 projection output.
Based on this project: https://github.com/Bullhill/agf-converter

## Features

- **Decryption**: Automatically handles AES-128-CBC decryption using the file's UUID.
- **Decompression**: Robustly handles GZIP/ZLIB compressed data streams.
- **Conversion**: Parses custom binary geometry formats (Points, Types 2 & 3 polygons) and converts ECEF coordinates to WGS84 (Lat/Lon).
- **Batch Processing**:
  - `convert_agf.py`: Converts all `.agf` files in the current directory.
  - `convert_zip.py`: Extracts `.zip` archives and recursively converts all contained `.agf` files.
- **GIS Ready**: generates `.prj` files so output is immediately usable in QGIS, ArcGIS, Google Earth, etc.

## Installation

This project uses `uv` or standard `pip`.

### Requirements

- Python 3.11+
- `cryptography`
- `pyproj`
- `pyshp`

### Setup

```bash
# Install dependencies
pip install cryptography pyproj pyshp

# Or using uv
uv sync
```

## Usage

### Single File / Directory Scan

Place your `.agf` files in the project directory and run:

```bash
python convert_agf.py
```

### Zip Archive processing

To process `AgData.zip` or other archives:

```bash
python convert_zip.py
```

Extracted shapefiles will be placed in `extracted_<zipname>/...`.

## Disclaimer

This tool is for educational and interoperability purposes. Ensure you have the right to access and process the data.
