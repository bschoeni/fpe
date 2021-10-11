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

# Package ff3 implements the FF3-1 format-preserving encryption algorithm/scheme

import logging
import math
from Crypto.Cipher import AES
import string

# The recommendation in Draft SP 800-38G was strengthened to a requirement in Draft SP 800-38G Revision 1:
# the minimum domain size for FF1 and FF3-1 is one million.
DOMAIN_MIN = 1_000_000  # 1M required in FF3-1
MAX_RADIX = 2 ** 16
NUM_ROUNDS = 8
BLOCK_SIZE = 16  # aes.BlockSize
TWEAK_LEN = 8  # Original FF3 tweak length
TWEAK_LEN_NEW = 7  # FF3-1 tweak length
HALF_TWEAK_LEN = TWEAK_LEN // 2
DEFAULT_ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase

NoneType = type(None)

def reverse_string(txt):
    """func defined for clarity"""
    return txt[::-1]

"""
FF3 encodes a string within a range of minLen..maxLen. The spec uses an alternating Feistel
with the following parameters:
    128 bit key length
    Cipher Block Chain (CBC-MAC) round function
    64-bit (FF3) or 56-bit (FF3-1)tweak
    eight (8) rounds
    Modulo addition

An encoded string representation of x is in the given integer base, which must be between 2 and 62, inclusive. The 
result uses the lower-case letters 'a' to 'z' for digit values 10 to 35 and upper-case letters 'A' to 'Z' for 
digit values 36 to 61.

FF3Cipher initializes a new FF3 Cipher object for encryption or decryption with key, tweak and radix parameters. The
default radix is 10, supporting encryption of decimal numbers.

AES ECB is used as the cipher round value for XORing. ECB has a block size of 128 bits (i.e 16 bytes) and is 
padded with zeros for blocks smaller than this size. ECB is used only in encrypt mode to generate this XOR value. 
A Feistel decryption uses the same ECB encrypt value to decrypt the text. XOR is trivially invertible when you 
know two of the arguments.
"""


class FF3Cipher:
    """Class FF3Cipher implements the FF3 format-preserving encryption algorithm"""
    def __init__(self, key, tweak, radix=None, alphabet=None):

        radix, alphabet = validate_radix_and_alphabet(radix, alphabet)

        keybytes = bytes.fromhex(key)
        self.tweak = tweak
        self.radix = radix
        self.alphabet = alphabet

        # Calculate range of supported message lengths [minLen..maxLen]
        self.minLen, self.maxLen = minlen_and_maxlen(radix)

        klen = len(keybytes)

        # Check if the key is 128, 192, or 256 bits = 16, 24, or 32 bytes
        if klen not in (16, 24, 32):
            raise ValueError(f'key length is {klen} but must be 128, 192, or 256 bits')

        # AES block cipher in ECB mode with the block size derived based on the length of the key
        # Always use the reversed key since Encrypt and Decrypt call ciph expecting that

        self.aesCipher = AES.new(reverse_string(keybytes), AES.MODE_ECB)

    @staticmethod
    def calculateP(i, alphabet, W, B):
        # P is always 16 bytes
        P = bytearray(BLOCK_SIZE)

        # Calculate P by XORing W, i into the first 4 bytes of P
        # i only requires 1 byte, rest are 0 padding bytes
        # Anything XOR 0 is itself, so only need to XOR the last byte

        P[0] = W[0]
        P[1] = W[1]
        P[2] = W[2]
        P[3] = W[3] ^ int(i)

        # The remaining 12 bytes of P are for rev(B) with padding

        BBytes = decode_int(B, alphabet).to_bytes(12, "big")
        # logging.debug(f"B: {B} BBytes: {BBytes.hex()}")

        P[BLOCK_SIZE - len(BBytes):] = BBytes
        return P

    def encrypt(self, plaintext):
        """Encrypts the plaintext string and returns a ciphertext of the same length and format"""
        return self.encrypt_with_tweak(plaintext, self.tweak)

    """
    Feistel structure

            u length |  v length
            A block  |  B block

                C <- modulo function

            B' <- C  |  A' <- B


    Steps:

    Let u = [n/2]
    Let v = n - u
    Let A = X[1..u]
    Let B = X[u+1,n]
    Let T(L) = T[0..31] and T(R) = T[32..63]
    for i <- 0..7 do
        If is even, let m = u and W = T(R) Else let m = v and W = T(L)
        Let P = REV([NUM<radix>(Rev(B))]^12 || W ⊗ REV(i^4)
        Let Y = CIPH(P)
        Let y = NUM<2>(REV(Y))
        Let c = (NUM<radix>(REV(A)) + y) mod radix^m
        Let C = REV(STR<radix>^m(c))
        Let A = B
        Let B = C
    end for
    Return A || B

    * Where REV(X) reverses the order of characters in the character string X

    See spec and examples:

    https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-38Gr1-draft.pdf
    https://csrc.nist.gov/CSRC/media/Projects/Cryptographic-Standards-and-Guidelines/documents/examples/FF3samples.pdf
    """

    # EncryptWithTweak allows a parameter tweak instead of the current Cipher's tweak

    def encrypt_with_tweak(self, plaintext, tweak):
        """Encrypts the plaintext string and returns a ciphertext of the same length and format"""
        tweakBytes = bytes.fromhex(tweak)

        n = len(plaintext)

        # Check if message length is within minLength and maxLength bounds
        if (n < self.minLen) or (n > self.maxLen):
            raise ValueError(f"message length {n} is not within min {self.minLen} and max {self.maxLen} bounds")

        # Make sure the given the length of tweak in bits is 56 or 64
        if len(tweakBytes) not in [TWEAK_LEN, TWEAK_LEN_NEW]:
            raise ValueError(f"tweak length {len(tweakBytes)} invalid: tweak must be 56 or 64 bits")

        # Todo: Check message is in current radix

        # Calculate split point
        u = math.ceil(n / 2)
        v = n - u

        # Split the message
        A = plaintext[:u]
        B = plaintext[u:]

        if len(tweakBytes) == TWEAK_LEN:
            # Split the tweak
            Tl = tweakBytes[:HALF_TWEAK_LEN]
            Tr = tweakBytes[HALF_TWEAK_LEN:]
        elif len(tweakBytes) == TWEAK_LEN_NEW:
            # Tl is T[0..27] + 0000
            Tl = bytearray(tweakBytes[:4])
            Tl[3] &= 0xF0

            # Tr is T[32..55] + T[28..31] + 0000
            Tr = bytearray((int(tweakBytes[4:].hex(), 16) << 4).to_bytes(4, 'big'))
            Tr[3] = tweakBytes[6] << 4 & 0xF0
        else:
            raise ValueError(f"tweak length {len(tweakBytes)} invalid: tweak must be 56 or 64 bits")

        logging.debug(f"Tweak: {tweak}, tweakBytes:{tweakBytes.hex()}")

        # Pre-calculate the modulus since it's only one of 2 values,
        # depending on whether i is even or odd

        modU = self.radix ** u
        modV = self.radix ** v
        logging.debug(f"modU: {modU} modV: {modV}")

        # Main Feistel Round, 8 times
        #
        # AES ECB requires the number of bits in the plaintext to be a multiple of
        # the block size. Thus, we pad the input to 16 bytes

        for i in range(NUM_ROUNDS):
            # logging.debug(f"-------- Round {i}")
            # Determine alternating Feistel round side
            if i % 2 == 0:
                m = u
                W = Tr
            else:
                m = v
                W = Tl

            # P is fixed-length 16 bytes
            P = FF3Cipher.calculateP(i, self.alphabet, W, B)
            revP = reverse_string(P)

            S = self.aesCipher.encrypt(bytes(revP))

            S = reverse_string(S)
            # logging.debug("S:    ", S.hex())

            y = int.from_bytes(S, byteorder='big')

            # Calculate c
            c = decode_int(A, self.alphabet)

            c = c + y

            if i % 2 == 0:
                c = c % modU
            else:
                c = c % modV

            # logging.debug(f"m: {m} A: {A} c: {c} y: {y}")
            C = encode_int_r(c, self.radix, int(m), self.alphabet)

            # Final steps
            A = B
            B = C

            # logging.debug(f"A: {A} B: {B}")

        return A + B

    def decrypt(self, ciphertext):
        """
        Decrypts the ciphertext string and returns a plaintext of the same length and format.

        The process of decryption is essentially the same as the encryption process. The  differences
        are  (1)  the  addition  function  is  replaced  by  a  subtraction function that is its
        inverse, and (2) the order of the round indices (i) is reversed.
        """
        return self.decrypt_with_tweak(ciphertext, self.tweak)

    def decrypt_with_tweak(self, ciphertext, tweak):
        """Decrypts the ciphertext string and returns a plaintext of the same length and format"""
        tweakBytes = bytes.fromhex(tweak)

        n = len(ciphertext)

        # Check if message length is within minLength and maxLength bounds
        if (n < self.minLen) or (n > self.maxLen):
            raise ValueError(f"message length {n} is not within min {self.minLen} and max {self.maxLen} bounds")

        # Make sure the given the length of tweak in bits is 56 or 64
        if len(tweakBytes) not in [TWEAK_LEN, TWEAK_LEN_NEW]:
            raise ValueError(f"tweak length {len(tweakBytes)} invalid: tweak must be 8 bytes, or 64 bits")

        # Todo: Check message is in current radix

        # Calculate split point
        u = math.ceil(n/2)
        v = n - u

        # Split the message
        A = ciphertext[:u]
        B = ciphertext[u:]

        # Split the tweak
        if len(tweakBytes) == TWEAK_LEN:
            # Split the tweak
            Tl = tweakBytes[:HALF_TWEAK_LEN]
            Tr = tweakBytes[HALF_TWEAK_LEN:]
        elif len(tweakBytes) == TWEAK_LEN_NEW:
            # Tl is T[0..27] + 0000
            Tl = bytearray(tweakBytes[:4])
            Tl[3] &= 0xF0

            # Tr is T[32..55] + T[28..31] + 0000
            Tr = bytearray((int(tweakBytes[4:].hex(), 16) << 4).to_bytes(4, 'big'))
            Tr[3] = tweakBytes[6] << 4 & 0xF0
        else:
            raise ValueError(f"tweak length {len(tweakBytes)} invalid: tweak must be 56 or 64 bits")

        logging.debug(f"Tweak: {tweak}, tweakBytes:{tweakBytes.hex()}")

        # Pre-calculate the modulus since it's only one of 2 values,
        # depending on whether i is even or odd

        modU = self.radix ** u
        modV = self.radix ** v
        logging.debug(f"modU: {modU} modV: {modV}")

        # Main Feistel Round, 8 times

        for i in reversed(range(NUM_ROUNDS)):

            # logging.debug(f"-------- Round {i}")
            # Determine alternating Feistel round side
            if i % 2 == 0:
                m = u
                W = Tr
            else:
                m = v
                W = Tl

            # P is fixed-length 16 bytes
            P = FF3Cipher.calculateP(i, self.alphabet, W, A)
            revP = reverse_string(P)

            S = self.aesCipher.encrypt(bytes(revP))
            S = reverse_string(S)

            # logging.debug("S:    ", S.hex())

            y = int.from_bytes(S, byteorder='big')

            # Calculate c
            c = decode_int(B, self.alphabet)

            c = c - y

            if i % 2 == 0:
                c = c % modU
            else:
                c = c % modV

            # logging.debug(f"m: {m} B: {B} c: {c} y: {y}")
            C = encode_int_r(c, self.radix, int(m), self.alphabet)

            # Final steps
            B = A
            A = C

            # logging.debug(f"A: {A} B: {B}")

        return A + B

def encode_int_r(n, base=2, length=0, alphabet=None):
    """
    Return a string representation of a number in the given base system for 2..62

    The string is left in a reversed order expected by the calling cryptographic function

    examples:
       radix_conv(5)
        '101'
       radix_conv(10, base=16)
        'A'
       radix_conv(32, base=16)
        '20'
    """
    base, alphabet = validate_radix_and_alphabet(base, alphabet)

    x = ''
    while n >= base:
        n, b = divmod(n, base)
        x += alphabet[b]
    x += alphabet[n]

    if len(x) < length:
        x = x.ljust(length, alphabet[0])

    return x

def decode_int(string, alphabet):
    """Decode a Base X encoded string into the number

    Arguments:
    - `string`: The encoded string
    - `alphabet`: The alphabet to use for decoding
    """
    strlen = len(string)
    base = len(alphabet)
    num = 0

    idx = 0
    for char in reverse_string(string):
        power = (strlen - (idx + 1))
        num += alphabet.index(char) * (base ** power)
        idx += 1

    return num

def validate_radix_and_alphabet(radix, alphabet):
    """Validate and compute radix and alphabet given one or the other.

    If only radix is given, use the default alphabet up to that many characters.
    If only alphabet is given, compute the radix as the length of the alphabet.
    If both are given, verify consistency.

    Arguments:
    - `radix`: The length of the alphabet
    - `alphabet`: A string containing successive characters to be used as digits

    Returns:
    - `radix`, `alphabet`: A validated tuple containing both the radix and alphabet
    """

    if not isinstance(radix, (NoneType, int)):
        raise ValueError(f"radix must be an integer.")

    if radix is not None and radix < 2:
        raise ValueError("radix must be at least 2.")

    if not isinstance(alphabet, (NoneType, str)):
        raise ValueError(f"alphabet must be an string.")

    if alphabet is not None and len(alphabet) < 2:
        raise ValueError(f"alphabet must contain at least two characters.")

    if radix is not None and alphabet is not None:
        # Verify consistency
        if len(alphabet) != radix:
            raise ValueError(
                f"The alphabet has length {len(alphabet)} which conflicts with "
                f"the given value of {radix} for radix."
            )

    if alphabet is None:
        if radix is None:
            radix = 10
        # Use characters from the default alphabet.
        if radix > len(DEFAULT_ALPHABET):
            raise ValueError(
                f"For radix >{len(DEFAULT_ALPHABET)} "
                f"please specify a custom alphabet."
            )
        alphabet = DEFAULT_ALPHABET[:radix]
    # alphabet is now defined. The radix might not be.

    if len(alphabet) != len(str(alphabet)):
        raise ValueError("The specified alphabet has duplicate characters.")

    if radix is None:
        radix = len(alphabet)
    # radix is now defined.

    if radix > MAX_RADIX:
        raise ValueError(
            f"The current radix {radix} exceeds the maximum allowed radix of "
            f"{MAX_RADIX} in the FF3-1 specification."
        )

    return radix, alphabet

def minlen_and_maxlen(radix):
        """Calculate range of supported message lengths [minLen..maxLen].

        Correctness of these formulas is verified in ff3_test.test_minlen_maxlen.
        """
        minLen = math.ceil(math.log(DOMAIN_MIN, radix))

        # maxLen = 2 * math.floor(math.log(2 ** 96, radix))

        # Simplify the above formula from the spec using the log base change rule.
        maxLen = 2 * math.floor(96 / math.log2(radix))

        return minLen, maxLen
