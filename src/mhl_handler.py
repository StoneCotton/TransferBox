import os
import xml.etree.ElementTree as ET
from datetime import datetime
import socket

def initialize_mhl_file(directory_name, target_dir):
    mhl_filename = os.path.join(target_dir, f"{directory_name}.mhl")
    root = ET.Element("hashlist", version="2.0", xmlns="urn:ASC:MHL:v2.0")

    creator_info = ET.SubElement(root, "creatorinfo")
    creation_date = ET.SubElement(creator_info, "creationdate")
    creation_date.text = datetime.now().isoformat()
    hostname = ET.SubElement(creator_info, "hostname")
    hostname.text = socket.gethostname()
    tool = ET.SubElement(creator_info, "TransferBox", version="0.1.0")
    tool.text = "TransferBox"

    process_info = ET.SubElement(root, "processinfo")
    process = ET.SubElement(process_info, "process")
    process.text = "in-place"
    roothash = ET.SubElement(process_info, "roothash")
    content = ET.SubElement(roothash, "content")
    structure = ET.SubElement(roothash, "structure")
    
    ignore = ET.SubElement(process_info, "ignore")
    for pattern in [".DS_Store", "ascmhl", "ascmhl/"]:
        ignore_pattern = ET.SubElement(ignore, "pattern")
        ignore_pattern.text = pattern

    hashes = ET.SubElement(root, "hashes")
    tree = ET.ElementTree(root)
    tree.write(mhl_filename, encoding='utf-8', xml_declaration=True)
    
    return mhl_filename, tree, hashes

def add_file_to_mhl(mhl_filename, tree, hashes, file_path, checksum, file_size):
    hash_element = ET.SubElement(hashes, "hash")
    path = ET.SubElement(hash_element, "path", size=str(file_size))
    path.text = os.path.relpath(file_path)
    last_modification_date = ET.SubElement(path, "lastmodificationdate")
    last_modification_date.text = datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()

    xxh64 = ET.SubElement(hash_element, "xxh64", action="original")
    xxh64.text = checksum
    xxh64.set("hashdate", datetime.now().isoformat())

    tree.write(mhl_filename, encoding='utf-8', xml_declaration=True)

