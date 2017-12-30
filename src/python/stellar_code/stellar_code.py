
import math

import astropy
import astropy.coordinates
import numpy

# Modified Open Location Code implementation.
# https://github.com/google/open-location-code

#A separator used to break the code into two parts to aid memorability.
SEPARATOR_ = '+'

#The number of characters to place before the separator.
SEPARATOR_POSITION_ = 12

#The character used to pad codes.
PADDING_CHARACTER_ = '0'

# The character set used to encode the values.
CODE_ALPHABET_ = '23456789CFGHJMPQRVWX'

# The base to use to convert numbers to/from.
ENCODING_BASE_ = len(CODE_ALPHABET_)

# Resolution values in parsec for each position in the XYZ
# triple encoding. These give the place value of each position,
# and therefore the dimensions of the resulting areas.
TRIPLE_RESOLUTIONS_ = [ENCODING_BASE_ ** x for x in reversed(range(0,5))]

# Maximum code length using XYZ triple encoding. The area of
# such a code is 1x1x1 parsec. This should be suitable for
# identifying small groups of star systems. This excludes
# prefix and separator characters.
TRIPLE_CODE_LENGTH_ = 15


def sol_galactic_coord():
    return astropy.coordinates.SkyCoord(x=0, y=0, z=0, unit='parsec', representation='cartesian').galactic


def sol_code():
    return encode_galactic(sol_galactic_coord())


def encode_galactic(c_galactic):
    # Sol is at the center of the encoding grid, but base 20 prevents encoding
    # a true center. Encoding defaults to flooring values. A location on a border
    # will encode to the lower value. Therfore, the first triple in the Sol code
    # is FFF (bottom left of center) while the rest of the triples are XXX
    # (top right of each subsequent sector). 

    offset = int(ENCODING_BASE_ * 0.5 * TRIPLE_RESOLUTIONS_[0])

    # Decrement by the smallest possible amount so (0,0,0) encodes to FFFXXXXXXXXX+XXX
    offset = numpy.nextafter(offset, offset-1)

    # Convert from zero based to center based.
    adjusted_x = math.floor(offset + c_galactic.cartesian.x.value)
    adjusted_y = math.floor(offset + c_galactic.cartesian.y.value)
    adjusted_z = math.floor(offset + c_galactic.cartesian.z.value)

    code = ''
    digit_count = 0
    while digit_count < TRIPLE_CODE_LENGTH_:
        place_value = TRIPLE_RESOLUTIONS_[int(math.floor(digit_count / 3))]
        
        digit_value = int(math.floor(adjusted_x / place_value))
        adjusted_x -= digit_value * place_value
        code += CODE_ALPHABET_[digit_value]
        digit_count += 1
        
        digit_value = int(math.floor(adjusted_y / place_value))
        adjusted_y -= digit_value * place_value
        code += CODE_ALPHABET_[digit_value]
        digit_count += 1

        digit_value = int(math.floor(adjusted_z / place_value))
        adjusted_z -= digit_value * place_value
        code += CODE_ALPHABET_[digit_value]
        digit_count += 1

        if digit_count == SEPARATOR_POSITION_:
            code += SEPARATOR_
    return code


def encode_equitorial(ra, dec, dist): 
    c_icrs = astropy.coordinates.SkyCoord(
            ra=ra * astropy.units.degree,
            dec=dec * astropy.units.degree,
            distance=dist * astropy.units.parsec)
    return encode_galactic(c_icrs.galactic)



