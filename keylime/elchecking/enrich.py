#!/usr/bin/python3

import oyaml
import sys
import re
import traceback
from ctypes import *

##################################################################################
#
# yaml by default outputs numbers in decimal format, and this allows us to
# represent some numbers in hexadecimal
#
##################################################################################

class hexint(int): pass

def representer(dumper, data):
	return oyaml.ScalarNode('tag:yaml.org,2002:int', hex(data))

oyaml.add_representer(hexint, representer)

##################################################################################
#
# Binary data from TSS will be in Little Endian according to the TPM spec, so
# we need to convert them to host byte order before hand
#
##################################################################################

##################################################################################
#
# These function use efivar C libraries to decode device path and guid
#
##################################################################################

efivarlib = "libefivar.so" # formerly "/usr/lib/x86_64-linux-gnu/libefivar.so"

efivarlib_functions = CDLL(efivarlib)

def getDevicePath(b):
	ret = efivarlib_functions.efidp_format_device_path(0, 0, b, len(b))
	if ret < 0:
		raise Exception(f'getDevicePath: efidp_format_device_path({b}) returned {ret}')

	s = create_string_buffer((ret+1))

	ret = efivarlib_functions.efidp_format_device_path(s, ret+1, b, len(b))
	if ret < 0:
		raise Exception(f'getDevicePath: efidp_format_device_path({b}) returned {ret}')

	return s.value.decode("utf-8")

def getGUID(b):
	s = c_char_p(None)
	ret = efivarlib_functions.efi_guid_to_str(b, byref(s))
	if ret < 0:
		raise Exception(f'getGUID: efi_guid_to_str({b}) returned {ret}')
	return s.value.decode("utf-8")

##################################################################################
#
# https://uefi.org/sites/default/files/resources/UEFI%20Spec%202.8B%20May%202020.pdf
# Section 32.4.1
#
# Relevant data structures
#
#  typedef struct _EFI_SIGNATURE_LIST {
#       uint8_t SignatureType[16];
#       uint32_t SignatureListSize;
#       uint32_t SignatureHeaderSize;
#       uint32_t SignatureSize;
#       // uint8_t SignatureHeader[SignatureHeaderSize];
#       // uint8_t Signatures[][SignatureSize];
#  } EFI_SIGNATURE_LIST;
#
#  typedef struct _EFI_SIGNATURE_DATA {
#      uint8_t SignatureOwner[16];
#      uint8_t SignatureData[];
#  } EFI_SIGNATURE_DATA;
#
##################################################################################

##################################################################################
# Print out EFI_SIGNATURE_DATA
##################################################################################
def getKey(b, start, size):
	key = {}
	signatureOwner = getGUID(b[start:start+16])
	key['SignatureOwner'] = signatureOwner

	signatureData = b[start+16:start+size]
	key['SignatureData'] = signatureData.hex()
	return key

##################################################################################
# Print out EFI_SIGNATURE_LIST
##################################################################################
def getKeyDB(b):
	keylists = []
	start = 0
	keydbLen = len(b)

	while start < keydbLen:
		# parse signature list
		keylist = {}
		i = start
		size = 16
		signatureType = b[i:i+size]
		keylist['SignatureType'] = getGUID(signatureType)

		i += size
		size = 4
		signatureListSize = b[i:i+size]
		keylist['SignatureListSize'] = int.from_bytes(signatureListSize, "little")

		i += size
		size = 4
		signatureHeaderSize = b[i:i+size]
		keylist['SignatureHeaderSize'] = int.from_bytes(signatureHeaderSize, "little")

		i += size
		size = 4
		signatureSize = b[i:i+size]
		keylist['SignatureSize'] = int.from_bytes(signatureSize, "little")

		# calculate how many bytes are for signatures
		sllen = keylist['SignatureListSize'] - 28 - keylist['SignatureHeaderSize']
		if sllen < 0:
			raise Exception(f'getKeyDB: SignatureListSize is too small {keylist["SignatureListSize"]}')

		if sllen % keylist['SignatureSize'] != 0:
			raise Exception(f'getKeyDB: SignatureListSize({sllen}) is not divisible by SignatureSize({keylist["SignatureSize"]})')

		numberOfSignatures = int(sllen / keylist['SignatureSize'])
		keys = []
		i += size
		for x in range(numberOfSignatures):
			key = getKey(b, i, keylist['SignatureSize'])
			i += keylist['SignatureSize']
			keys.append(key)
		keylist['Keys'] = keys

		start = i
		keylists.append(keylist)

	return keylists

##################################################################################
#
# https://uefi.org/sites/default/files/resources/UEFI%20Spec%202.8B%20May%202020.pdf
# Section 3.1.3
#
# Relevant data structures
#
#   typedef struct _EFI_LOAD_OPTION {
#       UINT32 Attributes;
#       UINT16 FilePathListLength;
#       // CHAR16 Description[];
#       // EFI_DEVICE_PATH_PROTOCOL FilePathList[];
#       // UINT8 OptionalData[];} EFI_LOAD_OPTION;
#   } EFI_LOAD_OPTION;
#
##################################################################################

##################################################################################
# Print additional information about variables BootOrder and Boot####
##################################################################################
def getVar(event, b):
	if 'UnicodeName' in event:
		if 'VariableDataLength' in event:
			varlen = event['VariableDataLength']

			# BootOrder variable
			if event['UnicodeName'] == 'BootOrder':
				if varlen % 2 != 0:
					raise Exception(f'getVar: VariableDataLength({varlen}) is not divisible by 2')

				l = int(varlen / 2)
				r = []
				for x in range(l):
					d = int.from_bytes(b[x*2:x*2+2], byteorder='little')
					r.append("Boot%04x" % d)
				return r
			# Boot#### variable
			elif re.match('Boot[0-9a-fA-F]{4}', event['UnicodeName']):
				r = {}
				i = 0
				size = 4
				attributes = b[i:i+size]
				d = int.from_bytes(attributes, "little") & 1
				if d == 0:
					r['Enabled'] = 'No'
				else:
					r['Enabled'] = 'Yes'

				i += size
				size = 2
				filePathListLength = b[i:i+size]
				d = int.from_bytes(filePathListLength, "little")
				r['FilePathListLength'] = d

				i += size
				size = 2
				description = ''
				while i < varlen:
					w = b[i:i+size]
					i += size
					if w == b'\x00\x00':
						break

					c = w.decode("utf-16", errors="ignore")
					description += c
				r['Description'] = description
				devicePath = getDevicePath(b[i:])
				r['DevicePath'] = devicePath
				return r

##################################################################################
#
# https://uefi.org/sites/default/files/resources/UEFI%20Spec%202.8B%20May%202020.pdf
# Section 5.3
#
# Relevant data structures
#
#   typedef struct tdUEFI_PARTITION_TABLE_HEADER {
#       uint64_t Signature;
#       uint32_t Revision;
#       uint32_t HeaderSize;
#       uint32_t HeaderCRC32;
#       uint32_t Reserved;
#       uint64_t MyLBA;
#       uint64_t AlternateLBA;
#       uint64_t FirstUsableLBA;
#       uint64_t LastUsableLBA;
#       uint8_t DiskGUID[16];
#       uint64_t PartitionEntryLBA;
#       uint32_t NumberOfPartitionEntries;
#       uint32_t SizeOfPartitionEntry;
#       uint32_t PartitionEntryArrayCRC32;
#   } UEFI_PARTITION_TABLE_HEADER;
#
#   typedef struct tdUEFI_PARTITION_ENTRY {
#       uint8_t PartitionTypeGUID[16];
#       uint8_t UniquePartitionGUID[16];
#       uint64_t StartingLBA;
#       uint64_t EndingLBA;
#       uint64_t Attributes;
#       uint8_t PartitionName[72];
#   } UEFI_PARTITION_ENTRY;
#
#   typedef struct tdUEFI_GPT_DATA {
#       UEFI_PARTITION_TABLE_HEADER UEFIPartitionHeader;
#       uint64_t NumberOfPartitions;
#       UEFI_PARTITION_ENTRY Partitions[];
#   } UEFI_GPT_DATA;
#
##################################################################################

##################################################################################
# Print Guid Partition Table (GPT) information
##################################################################################
def getGPT(b):

	varlen = len(b)
	gpt = {}
	header = {}

	# Parse UEFI_PARTITION_TABLE_HEADER

	# Signature seems to be a character string
	i = 0
	size = 8
	signature = b[i:i+size]
	header['Signature'] = signature.decode("utf-8", errors="ignore")
	gpt['Header'] = header

	i += size
	size = 4
	revision = b[i:i+size]
	header['Revision'] = hexint(int.from_bytes(revision, "little"))

	i += size
	size = 4
	headerSize = b[i:i+size]
	header['HeaderSize'] = int.from_bytes(headerSize, "little")

	i += size
	size = 4
	headerCRC= b[i:i+size]
	header['HeaderCRC32'] = hexint(int.from_bytes(headerCRC, "little"))

	# Reserved field
	i += size
	size = 4

	i += size
	size = 8
	myLBA = b[i:i+size]
	header['MyLBA'] = hexint(int.from_bytes(myLBA, "little"))

	i += size
	size = 8
	alternateLBA = b[i:i+size]
	header['AlternateLBA'] = hexint(int.from_bytes(alternateLBA, "little"))

	i += size
	size = 8
	firstUsableLBA = b[i:i+size]
	header['FirstUsableLBA'] = hexint(int.from_bytes(firstUsableLBA, "little"))

	i += size
	size = 8
	lastUsableLBA = b[i:i+size]
	header['LastUsableLBA'] = hexint(int.from_bytes(lastUsableLBA, "little"))

	i += size
	size = 16
	diskGUID = getGUID(b[i:i+size])
	header['DiskGuid'] = diskGUID

	i += size
	size = 8
	partitionEntryLBA = b[i:i+size]
	header['PartitionEntryLBA'] = hexint(int.from_bytes(partitionEntryLBA, "little"))

	i += size
	size = 4
	numberOfPartitionEntries = b[i:i+size]
	header['NumberOfPartitionEntries'] = int.from_bytes(numberOfPartitionEntries, "little")

	i += size
	size = 4
	sizeOfPartitionEntry = b[i:i+size]
	header['SizeOfPartitionEntry'] = int.from_bytes(sizeOfPartitionEntry, "little")

	i += size
	size = 4
	partitionEntryArrayCRC = b[i:i+size]
	header['PartitionEntryArrayCRC'] = hexint(int.from_bytes(partitionEntryArrayCRC, "little"))

	gpt['Header'] = header

	# Parse NumberOfPartitions;

	i += size
	size = 8
	numberOfPartitions = b[i:i+size]
	gpt['NumberOfPartitions'] = int.from_bytes(numberOfPartitions, "little")

	i += size

	partitions = []
	for x in range(gpt['NumberOfPartitions']):
		partition = {}

		start = i
		size = 16
		partitionTypeGUID = getGUID(b[i:i+size])
		partition['PartitionTypeGUID'] = partitionTypeGUID

		i += size
		size = 16
		uniquePartitionGUID = getGUID(b[i:i+size])
		partition['UniquePartitionGUID'] = uniquePartitionGUID

		i += size
		size = 8
		startingLBA = b[i:i+size]
		partition['StartingLBA'] = hexint(int.from_bytes(startingLBA, "little"))

		i += size
		size = 8
		endingLBA = b[i:i+size]
		partition['EndingLBA'] = hexint(int.from_bytes(endingLBA, "little"))

		i += size
		size = 8
		attributes = b[i:i+size]
		partition['Attributes'] = hexint(int.from_bytes(attributes, "little"))

		i += size
		# save the start of PartitionName
		j = i
		size = 2
		partitionName = ''
		while i < start + 128:
			w = b[i:i+size]
			i += size
			if w == b'\x00\x00':
				break

			c = w.decode("utf-16", errors="ignore")
			partitionName += c
		partition['PartitionName'] = partitionName
		# skip to the end of PartitionName
		i = j + 72

		partitions.append(partition)

	gpt['Partitions'] = partitions

	return gpt

def enrich(log):
	if 'events' in log:
		events = log['events']

		for event in events:
			if 'EventType' in event:
				t = event['EventType']
				if (t == 'EV_EFI_BOOT_SERVICES_APPLICATION' or
					t == 'EV_EFI_BOOT_SERVICES_DRIVER' or
					t == 'EV_EFI_RUNTIME_SERVICES_DRIVER'):
					if 'Event' in event:
						d = event['Event']
						if 'DevicePath' in d:
							b = bytes.fromhex(d['DevicePath'])
							try:
								p = getDevicePath(b)
							# Deal with garbage devicePath
							except Exception:
								p = f"{d['DevicePath']}"
							d['DevicePath'] = p
				elif t == 'EV_EFI_VARIABLE_DRIVER_CONFIG':
					if 'Event' in event:
						d = event['Event']
						if 'UnicodeName' in d:
							if (d['UnicodeName'] == 'PK' or
								d['UnicodeName'] == 'KEK' or
								d['UnicodeName'] == 'db' or
								d['UnicodeName'] == 'dbx'):
								if 'VariableData' in d:
									b = bytes.fromhex(d['VariableData'])
									k = getKeyDB(b)
									d['VariableData'] = k
							elif d['UnicodeName'] == 'SecureBoot':
								if 'VariableData' in d:
									b = bytes.fromhex(d['VariableData'])
									if len(b) == 0:
										d['VariableData'] = {'Enabled': 'No'}
									elif len(b) > 1:
										raise Exception(f'enrich: SecureBoot data length({len(b)}) > 1')
									else:
										if b == b'\x00':
											d['VariableData'] = {'Enabled': 'No'}
										else:
											d['VariableData'] = {'Enabled': 'Yes'}
				elif t == 'EV_EFI_VARIABLE_AUTHORITY':
					if 'Event' in event:
						d = event['Event']
						if 'VariableData' in d:
							b = bytes.fromhex(d['VariableData'])
							l = len(b)
							k = getKey(b, 0, l)
							d['VariableData'] = k
				elif t == 'EV_EFI_VARIABLE_BOOT':
					if 'Event' in event:
						d = event['Event']
						if 'VariableData' in d:
							b = {}
							b = bytes.fromhex(d['VariableData'])
							k = getVar(d, b)
							d['VariableData'] = k
				elif t == 'EV_EFI_GPT_EVENT':
					if 'Event' in event:
						b = bytes.fromhex(event['Event'])
						k = getGPT(b)
						event['Event'] = k

if __name__ == '__main__':
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
	parser.add_argument('-o', '--output', choices=('yaml', 'json'), default='yaml')
	args = parser.parse_args()
	log = oyaml.load(args.infile, Loader=oyaml.FullLoader)
	try:
		enrich(log)
	except Exception as e:
		traceback.print_exc(file=sys.stderr)
		sys.exit(1)
	if args.output == 'yaml':
		print(oyaml.dump(log, default_flow_style=False, line_break=None))
	elif args.output == 'json':
		import json
		print(json.dumps(log, sort_keys=True, indent=4))
	else:
		raise Exception(f'unexpected output format {args.output!a}')
