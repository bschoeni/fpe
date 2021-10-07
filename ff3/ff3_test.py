"""

SPDX-Copyright: Copyright (c) Schoening Consulting, LLC
SPDX-License-Identifier: Apache-2.0
Copyright 2021 Schoening Consulting, LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and limitations under the License.

"""

import unittest

from Crypto.Cipher import AES

from ff3 import FF3Cipher, encode_int_r, decode_int
from ff3 import reverse_string

# Test vectors taken from here: http://csrc.nist.gov/groups/ST/toolkit/documents/Examples/FF3samples.pdf

testVectors = [
    # AES-128
    {
        "radix": 10,
        "key": "EF4359D8D580AA4F7F036D6F04FC6A94",
        "tweak": "D8E7920AFA330A73",
        "plaintext": "890121234567890000",
        "ciphertext": "750918814058654607"
    },
    {
        "radix": 10,
        "key": "EF4359D8D580AA4F7F036D6F04FC6A94",
        "tweak": "9A768A92F60E12D8",
        "plaintext": "890121234567890000",
        "ciphertext": "018989839189395384",
    },
    {
        "radix": 10,
        "key": "EF4359D8D580AA4F7F036D6F04FC6A94",
        "tweak": "D8E7920AFA330A73",
        "plaintext": "89012123456789000000789000000",
        "ciphertext": "48598367162252569629397416226",
    },
    {
        "radix": 10,
        "key": "EF4359D8D580AA4F7F036D6F04FC6A94",
        "tweak": "0000000000000000",
        "plaintext": "89012123456789000000789000000",
        "ciphertext": "34695224821734535122613701434",
    },
    {
        "radix": 26,
        "key": "EF4359D8D580AA4F7F036D6F04FC6A94",
        "tweak": "9A768A92F60E12D8",
        "plaintext": "0123456789abcdefghi",
        "ciphertext": "g2pk40i992fn20cjakb",
    },

    # AES - 192
    {
        "radix": 10,
        "key": "EF4359D8D580AA4F7F036D6F04FC6A942B7E151628AED2A6",
        "tweak": "D8E7920AFA330A73",
        "plaintext": "890121234567890000",
        "ciphertext": "646965393875028755",
    },
    {
        "radix": 10,
        "key": "EF4359D8D580AA4F7F036D6F04FC6A942B7E151628AED2A6",
        "tweak": "9A768A92F60E12D8",
        "plaintext": "890121234567890000",
        "ciphertext": "961610514491424446",
    },
    {
        "radix": 10,
        "key": "EF4359D8D580AA4F7F036D6F04FC6A942B7E151628AED2A6",
        "tweak": "D8E7920AFA330A73",
        "plaintext": "89012123456789000000789000000",
        "ciphertext": "53048884065350204541786380807",
    },
    {
        "radix": 10,
        "key": "EF4359D8D580AA4F7F036D6F04FC6A942B7E151628AED2A6",
        "tweak": "0000000000000000",
        "plaintext": "89012123456789000000789000000",
        "ciphertext": "98083802678820389295041483512",
    },
    {
        "radix": 26,
        "key": "EF4359D8D580AA4F7F036D6F04FC6A942B7E151628AED2A6",
        "tweak": "9A768A92F60E12D8",
        "plaintext": "0123456789abcdefghi",
        "ciphertext": "i0ihe2jfj7a9opf9p88",
    },

    # AES - 256
    {
        "radix": 10,
        "key": "EF4359D8D580AA4F7F036D6F04FC6A942B7E151628AED2A6ABF7158809CF4F3C",
        "tweak": "D8E7920AFA330A73",
        "plaintext": "890121234567890000",
        "ciphertext": "922011205562777495",
    },
    {
        "radix": 10,
        "key": "EF4359D8D580AA4F7F036D6F04FC6A942B7E151628AED2A6ABF7158809CF4F3C",
        "tweak": "9A768A92F60E12D8",
        "plaintext": "890121234567890000",
        "ciphertext": "504149865578056140",
    },
    {
        "radix": 10,
        "key": "EF4359D8D580AA4F7F036D6F04FC6A942B7E151628AED2A6ABF7158809CF4F3C",
        "tweak": "D8E7920AFA330A73",
        "plaintext": "89012123456789000000789000000",
        "ciphertext": "04344343235792599165734622699",
    },
    {
        "radix": 10,
        "key": "EF4359D8D580AA4F7F036D6F04FC6A942B7E151628AED2A6ABF7158809CF4F3C",
        "tweak": "0000000000000000",
        "plaintext": "89012123456789000000789000000",
        "ciphertext": "30859239999374053872365555822",
    },
    {
        "radix": 26,
        "key": "EF4359D8D580AA4F7F036D6F04FC6A942B7E151628AED2A6ABF7158809CF4F3C",
        "tweak": "9A768A92F60E12D8",
        "plaintext": "0123456789abcdefghi",
        "ciphertext": "p0b2godfja9bhb7bk38",
    }
]


class TestFF3(unittest.TestCase):

    def test_base_repr(self):
        self.assertEqual(reverse_string(encode_int_r(5)), '101')
        self.assertEqual(reverse_string(encode_int_r(6, 5)), '11')
        self.assertEqual(reverse_string(encode_int_r(7, 5, 5)), '00012')
        self.assertEqual(reverse_string(encode_int_r(10, 16)), 'a')
        self.assertEqual(reverse_string(encode_int_r(32, 16)), '20')

    def test_aes_ecb(self):
        # NIST test vector for ECB-AES128
        key = bytes.fromhex('2b7e151628aed2a6abf7158809cf4f3c')
        pt = bytes.fromhex('6bc1bee22e409f96e93d7e117393172a')
        c = AES.new(key, AES.MODE_ECB)
        ct = c.encrypt(pt)
        self.assertEqual(ct.hex(), '3ad77bb40d7a3660a89ecaf32466ef97')

    def test_calculateP(self):
        # NIST Sample  # 1, round 0
        i = 0
        radix = 10
        b = "567890000"
        w = bytes.fromhex("FA330A73")
        p = FF3Cipher.calculateP(i, radix, w, b)
        self.assertEqual(p, bytes([250, 51, 10, 115, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 129, 205]))

    def test_encrypt_boundaries(self):
        c = FF3Cipher("EF4359D8D580AA4F7F036D6F04FC6A94", "D8E7920AFA330A73")
        # test max length 56 digit string with default radix 10
        plaintext = "12345678901234567890123456789012345678901234567890123456"
        ct = c.encrypt(plaintext)
        pt = c.decrypt(ct)
        self.assertEqual(plaintext, pt)
        # test max length 40 alphanumeric string with radix 26
        c = FF3Cipher("EF4359D8D580AA4F7F036D6F04FC6A94", "D8E7920AFA330A73", 26)
        plaintext = "0123456789abcdefghijklmn"
        ct = c.encrypt(plaintext)
        pt = c.decrypt(ct)
        self.assertEqual(plaintext, pt)
        # test max length 36 alphanumeric string with radix 36
        c = FF3Cipher("EF4359D8D580AA4F7F036D6F04FC6A94", "D8E7920AFA330A73", 36)
        plaintext = "abcdefghijklmnopqrstuvwxyz0123456789"
        ct = c.encrypt(plaintext)
        pt = c.decrypt(ct)
        self.assertEqual(plaintext, pt)

    def test_encrypt_all(self):
        for testVector in testVectors:
            with self.subTest(testVector=testVector):
                c = FF3Cipher(testVector['key'], testVector['tweak'], testVector['radix'])
                s = c.encrypt(testVector['plaintext'])
                self.assertEqual(s, testVector['ciphertext'])

    def test_decrypt_all(self):
        for testVector in testVectors:
            with self.subTest(testVector=testVector):
                c = FF3Cipher(testVector['key'], testVector['tweak'], testVector['radix'])
                s = c.decrypt(testVector['ciphertext'])
                self.assertEqual(s, testVector['plaintext'])

    # TODO: NIST announced in SP 800 38G Revision 1, the "the tweak parameter is reduced to 56 bits,
    #   in a manner that was subsequently developed by the designers of the method."

    # experimental test with 56 bit tweak
    def test_encrypt_tweak56(self):
        # 56-bit tweak
        tweak = "D8E7920AFA330A"
        ciphertext = "428531276362567922"
        testVector = testVectors[0]
        c = FF3Cipher(testVector['key'], tweak)
        s = c.encrypt(testVector['plaintext'])
        self.assertEqual(s, ciphertext)
        x = c.decrypt(s)
        self.assertEqual(x, testVector['plaintext'])

    # experimental test with 56 bit tweak from Bouncy Castle FF3-1 tests
    # Note: the ciphertext here does not match the BC value

    def test_encrypt_tweak56_bc(self):
        # 56-bit tweak
        key = "1A58964B681384806A5A7639915ED0BE837C9C50C150AFD8F73445C0438CACF3"
        tweak = "CE3EBD69454984"
        plaintext = "4752683571"
        # ciphertext = "2234571788"
        c = FF3Cipher(key, tweak)
        s = c.encrypt(plaintext)
        # self.assertEqual(s, ciphertext)
        x = c.decrypt(s)
        self.assertEqual(x, plaintext)


    # Check that encryption and decryption are inverses over whole domain
    def test_whole_domain(self):
        # Temporarily reduce DOMAIN_MIN to make testing fast
        from ff3 import ff3
        domain_min_orig = ff3.DOMAIN_MIN
        ff3.DOMAIN_MIN = ff3.RADIX_MAX + 1

        key = "EF4359D8D580AA4F7F036D6F04FC6A94"
        tweak = "D8E7920AFA330A73"
        for radix, working_digits in [(2, 10), (3, 6), (10, 3), (17, 3), (62, 2)]:
            c = FF3Cipher(key, tweak, radix=radix)
            self.subTest(radix=radix, working_digits=working_digits)
            n = radix ** working_digits
            perm = [decode_int(c.decrypt(c.encrypt(
                        encode_int_r(i, base=radix, length=working_digits))
                    ), radix) for i in range(n)]
            self.assertEqual(perm, list(range(n)))

        # Restore original DOMAIN_MIN value
        ff3.DOMAIN_MIN = domain_min_orig

if __name__ == '__main__':
    unittest.main()
