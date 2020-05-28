#!/usr/bin/python3

'''
SPDX-License-Identifier: BSD-2-Clause
Copyright 2017 Massachusetts Institute of Technology.
'''

import sys
import os
import base64

from keylime import crypto

def usage():
	print("please pass in a file input file to encrypt")
	sys.exit(-1)

def encrypt(contents):
	k = crypto.generate_random_key(32)
	v = crypto.generate_random_key(32)
	u = crypto.strbitxor(k,v)
	ciphertext= crypto.encrypt(contents,k)

	try:
	   recovered = crypto.decrypt(ciphertext,k).decode('utf-8')
	except UnicodeDecodeError:
		recovered = crypto.decrypt(ciphertext,k)

	if recovered != contents:
		raise Exception("Test decryption failed")
	return {'u':u,'v':v,'k':k,'ciphertext':ciphertext}

def main(argv=sys.argv):
	if len(argv)<2:
		usage()

	infile = argv[1]

	if not os.path.isfile(infile):
		print("ERROR: File %s not found."%infile)
		usage()

	f = open(infile,'r')
	contents = f.read()

	ret = encrypt(contents)

	print("Writing keys to content_keys.txt")
	f = open('content_keys.txt','w')
	f.write(base64.b64encode(ret['k']))
	f.write('\n')
	f.write(base64.b64encode(ret['v']))
	f.write('\n')
	f.write(base64.b64encode(ret['u']))
	f.write('\n')
	f.close()

	print("Writing encrypted data to content_payload.txt")
	f = open('content_payload.txt','w')
	f.write(ret['ciphertext'])
	f.close()


if __name__ == "__main__":
	main()
