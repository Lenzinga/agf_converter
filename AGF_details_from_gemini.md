# AGF File Format Specification

## Part 1: The High-Level Concept (Simple)

Think of an `.agf` file not as a single document, but as a digital suitcase.

### The Suitcase (ZIP Archive)
If you rename the file from `.agf` to `.zip`, you can open it.
Inside, you won't find a map file immediately. Instead, you will find folders organized by field or task name.

### The Packing List (Manifest)
In every folder, there is a readable file called `manifest.xml`. This acts like a packing list.
It tells the software:
*   What the field is named.
*   Which "locked box" contains the actual data.
*   **Crucially**: It contains the "serial number" (UUID) needed to create the key to open the locked box.

### The Locked Box (Encrypted Data)
The actual map data (boundaries, guidance lines) is inside a file that looks like gibberish (e.g., `.xml.gz.enc`).
It is locked using encryption (AES). The key to this lock isn't stored in the file; the software has to build the key using the serial number from the packing list and a secret "master code" hidden in the software itself.

### The Contents (Space Coordinates)
Once unlocked, the data inside isn't written as standard GPS latitude/longitude (like 48.85, 2.35). Instead, it uses **Earth-Centered Cartesian coordinates** (X, Y, Z in meters from the center of the Earth).
This is how satellites "think," but it requires conversion to be shown on a standard map.

---

## Part 2: Technical Deep Dive

This section details the byte-level architecture, encryption vectors, and geometry serialization.

### 1. The Container Layer

*   **Format**: Standard ZIP Archive (Deflate algorithm).
*   **File Signature**: `PK\x03\x04` (standard ZIP header).
*   **Directory Structure**:

```text
root.agf (ZIP)
└── [UUID_Folder_Name]
    ├── manifest.xml       <-- Plaintext Metadata & Crypto Parameters
    └── [UUID].xml.gz.enc  <-- The Encrypted Payload
```

### 2. The Security Layer (AES-CBC)

The payload is encrypted using **AES-128-CBC** (Cipher Block Chaining). To read the file, the decryptor must reconstruct the symmetric key.

*   **Initialization Vector (IV)**: Stored in plaintext in `manifest.xml` at XPath `/manifest/key/iv`. It is a 128-bit (16-byte) hex string.
*   **Key Derivation Function (KDF)**: The AES Key is not stored. It is derived using a bitwise XOR operation between the file's UUID and a static vendor constant.
    *   **Input 1**: The `uuid` from `manifest.xml` (Strip dashes `-`).
    *   **Input 2**: The Static Master Key (Hex): `e989715d4caa119b5fc8eac3ac46b7c3`.
    *   **Operation**: $Key_{128} = UUID_{hex} \oplus Master_{hex}$

### 3. The Payload Layer (Gzipped XML)

Once decrypted, the resulting bytestream is a GZIP file (`.gz`).

*   **Decompression**: Standard Gzip (RFC 1952).
*   **Result**: A raw XML file.
*   **Key XML Tags**:
    *   `<field_extent>`: Typically stores the boundary polygon.
    *   `<line>`: Guidance paths or AB lines.
*   **Data Format**: The content of these tags is Base64 encoded.

### 4. The Geometry Layer (Binary Serialization)

This is the most complex part. The Base64 string decodes into a proprietary binary structure representing geometry in the ECEF (Earth-Centered, Earth-Fixed) coordinate system.

**Binary Structure (Little-Endian):**

*   **Header (1 Byte)**: Defines the Geometry Type.
    *   `0x00`: Point
    *   `0x01`: LineString
    *   `0x03`: Polygon
    *   `0x04`: MultiPolygon

*   **Body (Variable, based on Header)**:
    *   **If Point (0x00)**:
        *   X (8 bytes, Double, Little-Endian)
        *   Y (8 bytes, Double, Little-Endian)
        *   Z (8 bytes, Double, Little-Endian)
        *   *Total Size*: 25 bytes (1 header + 24 data)
    *   **If Polygon (0x03)**:
        *   PointCount (4 bytes, Int32, Little-Endian)
        *   Array of Points: Sequence of [X, Y, Z] doubles repeated PointCount times.
    *   **If MultiPolygon (0x04)**:
        *   PolyCount (4 bytes, Int32, Little-Endian)
        *   Recursive Structure: PolyCount iterations of the Polygon structure above.
        *   *Note*: Sometimes nested structures repeat the Type Byte (`0x03`) inside the loop, requiring the parser to "peek" ahead.

### 5. Coordinate System (ECEF to WGS84)

The coordinates unpacked from the binary are **ECEF (EPSG:4978)**.

*   **Unit**: Meters.
*   **Origin**: Center of mass of the Earth.
*   **Conversion Required**: To get usable map data (Latitude $\phi$, Longitude $\lambda$, Altitude $h$), you must apply a geodetic transformation (typically Helmert transformation or standard inverse formulas):

$$
\begin{aligned}
x &= (N(\phi) + h) \cos \phi \cos \lambda \\
y &= (N(\phi) + h) \cos \phi \sin \lambda \\
z &= (N(\phi) (1 - e^2) + h) \sin \phi
\end{aligned}
$$

(Where $N(\phi)$ is the prime vertical radius of curvature and $e$ is the eccentricity of the ellipsoid).

### Summary Architecture Table

| Layer | Technology | Details |
| :--- | :--- | :--- |
| **Archive** | ZIP | Standard Deflate |
| **Crypto** | AES-128-CBC | Key derived via XOR of UUID |
| **Compression** | GZIP | Applied after XML generation, before encryption |
| **Serialization** | XML + Base64 | Geometry hidden in Base64 strings |
| **Geometry** | Binary Struct | Little-Endian Doubles (64-bit) |
| **Coordinates** | ECEF | X/Y/Z Meters (Requires WGS84 transform) |
