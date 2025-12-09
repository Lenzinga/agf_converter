import os
import zipfile
import xml.etree.ElementTree as ET
import base64
import struct
import gzip
import io
import binascii
import zlib

# Libraries for Crypto and GIS
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from pyproj import Transformer
import shapefile  # pyshp

# --- CONSTANTS ---
MASTER_XOR_KEY_HEX = "e989715d4caa119b5fc8eac3ac46b7c3"

def derive_key(uuid_str):
    """
    Derives the AES decryption key by XORing the UUID (sans dashes) 
    with the static Master Key.
    """
    # Remove dashes from UUID
    uuid_clean = uuid_str.replace("-", "").lower()
    
    # Convert hex strings to byte arrays
    uuid_bytes = binascii.unhexlify(uuid_clean)
    master_bytes = binascii.unhexlify(MASTER_XOR_KEY_HEX)
    
    # XOR operation
    key_bytes = bytearray()
    for b1, b2 in zip(uuid_bytes, master_bytes):
        key_bytes.append(b1 ^ b2)
        
    return bytes(key_bytes)

def decrypt_aes_cbc(ciphertext, key, iv_hex):
    """
    Decrypts AES-128-CBC ciphertext.
    """
    iv = binascii.unhexlify(iv_hex)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    return decryptor.update(ciphertext) + decryptor.finalize()

def parse_geometry_blob(blob):
    """
    Parses the custom binary geometry format used inside the XML tags.
    Format:
    Byte 0: Type (0=Point, 1=Line, 3=Polygon, 4=MultiPolygon)
    Then standard struct unpacking of doubles (ECEF X, Y, Z).
    """
    data = base64.b64decode(blob)
    offset = 0
    
    # Read Geometry Type
    geom_type = data[offset]
    offset += 1
    
    geometries = []
    
    def read_point(o):
        # 3 doubles (8 bytes each) = 24 bytes
        x, y, z = struct.unpack_from('<ddd', data, o)
        return (x, y, z), o + 24

    if geom_type == 4: # MultiPolygon
        poly_count, = struct.unpack_from('<i', data, offset)
        offset += 4
        for _ in range(poly_count):
            # Recurse for Polygon (Type 3 usually) inside Multi
            # The structure often nests; for simplified AGF, 
            # we assume the next byte is the type 3 header again or just point count.
            # Based on forum analysis: "MultiPolygon (b0=3) -> (int polyCount) -> goto Polygon"
            
            # Check if there is a nested type byte (common in recursive structures)
            sub_type = data[offset]
            if sub_type == 3: 
                offset += 1
            
            # Read Point Count for this polygon
            point_count, = struct.unpack_from('<i', data, offset)
            offset += 4
            
            ring = []
            for _ in range(point_count):
                pt, offset = read_point(offset)
                ring.append(pt)
            geometries.append(ring)
            
    elif geom_type == 3 or geom_type == 2: # Polygon or LineRing?
        point_count, = struct.unpack_from('<i', data, offset)
        offset += 4
        ring = []
        for _ in range(point_count):
            pt, offset = read_point(offset)
            ring.append(pt)
        geometries.append(ring)

    return geometries

def convert_ecef_to_lla(coords_list):
    """
    Converts a list of (X, Y, Z) ECEF coordinates to (Lon, Lat).
    """
    # Transformer: ECEF (EPSG:4978) -> WGS84 (EPSG:4326)
    transformer = Transformer.from_crs("EPSG:4978", "EPSG:4326", always_xy=True)
    
    lla_poly = []
    for (x, y, z) in coords_list:
        lon, lat, alt = transformer.transform(x, y, z)
        lla_poly.append([lon, lat]) # Shapefile expects [lon, lat]
    return lla_poly

def process_agf(agf_path):
    base_dir = os.path.dirname(agf_path)
    filename = os.path.basename(agf_path).split('.')[0]
    
    print(f"Processing: {agf_path}")
    
    with zipfile.ZipFile(agf_path, 'r') as z:
        # Find manifest (it's inside a folder in the zip)
        manifest_file = [f for f in z.namelist() if f.endswith('manifest.xml')][0]
        manifest_data = z.read(manifest_file)
        
        # Parse Manifest
        root = ET.fromstring(manifest_data)
        uuid = root.find('.//uuid').text
        iv = root.find('.//iv').text
        enc_filename = root.find('.//entry').text
        
        print(f"  UUID: {uuid}")
        print(f"  IV: {iv}")
        
        # Derive Key
        key = derive_key(uuid)
        print(f"  Derived Key: {binascii.hexlify(key).decode()}")
        
        # Find the encrypted file in the zip
        # The manifest path might differ slightly from zip structure, search by name
        enc_zip_path = [f for f in z.namelist() if enc_filename in f][0]
        enc_data = z.read(enc_zip_path)
        
        # Decrypt
        decrypted_gz = decrypt_aes_cbc(enc_data, key, iv)
        
        # Decompress GZIP (using zlib to ignore trailing garbage)
        try:
            xml_content = zlib.decompress(decrypted_gz, 16 + zlib.MAX_WBITS)
        except Exception as e:
            print(f"  Decompression failed: {e}")
            return

        # Parse the Decrypted XML
        decrypted_root = ET.fromstring(xml_content)
        
        # Extract Geometry
        # We look specifically for <field_extent> which usually holds the boundary
        extent_tags = decrypted_root.findall('.//field_extent')
        
        if not extent_tags:
            # Fallback for newer AGF versions using <geometry> inside <boundary>
            extent_tags = decrypted_root.findall('.//geometry')
            
        if not extent_tags:
            print(f"  No <field_extent> or <geometry> found in XML.")
            return

        # Initialize Shapefile Writer (Polygon)
        shp_writer = shapefile.Writer(os.path.join(base_dir, f"{filename}_boundary"), shapefile.POLYGON)
        shp_writer.field('ID', 'N')
        
        count = 0
        for tag in extent_tags:
            blob = tag.text
            if not blob: continue
            
            # Parse Binary Blob to ECEF Coords
            ecef_polys = parse_geometry_blob(blob)
            
            for poly in ecef_polys:
                # Convert to Lat/Lon
                lla_poly = convert_ecef_to_lla(poly)
                
                # Write to Shapefile
                # pyshp expects a list of lists of points [[x,y], [x,y]...]
                shp_writer.poly([lla_poly])
                shp_writer.record(count)
                count += 1
                
        shp_writer.close()
        
        # Write .prj file for EPSG:4326 (WGS84)
        prj_path = os.path.join(base_dir, f"{filename}_boundary.prj")
        wgs84_wkt = 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]]'
        with open(prj_path, "w") as f:
            f.write(wgs84_wkt)
            
        print(f"  Success! Exported {count} polygons to {filename}_boundary.shp (and .prj)")

