from machine import Pin, mem32
import sys, time

#constants
LED_ON_TIME = 5000 #us
DIGIT_DELAY =    0 #us

#register addresses
GPIO_SIO_ADDR = 0xd0000000
GPIO_IN       = 0x004
GPIO_OUT      = 0x010
GPIO_OUT_SET  = 0x014
GPIO_OUT_CLR  = 0x018
GPIO_OUT_XOR  = 0x01c

#GPIO register sample
GPIO = 0b00000000000000000000000000000000

#7-segment map:
#  AAAA
# F    B
# F    B
#  GGGG
# E    C
# E    C
#  DDDD   P

CHARS = {
# STR  0bABCDEFGP, #ASCII CHAR   Note
  "0": 0b11111100, # 48   '0'
  "1": 0b01100000, # 49   '1'
  "2": 0b11011010, # 50   '2'
  "3": 0b11110010, # 51   '3'
  "4": 0b01100110, # 52   '4'
  "5": 0b10110110, # 53   '5'
  "6": 0b10111110, # 54   '6'
  "7": 0b11100000, # 55   '7'
  "8": 0b11111110, # 56   '8'
  "9": 0b11110110, # 57   '9'
  'A': 0b11101110, # 65   'A'
  'B': 0b00111110, # 66   'b'
  'C': 0b10011100, # 67   'C'
  'D': 0b01111010, # 68   'd'
  'E': 0b10011110, # 69   'E'
  'F': 0b10001110, # 70   'F'
  'G': 0b10111100, # 71   'G'
  'H': 0b01101110, # 72   'H'
  'I': 0b00001100, # 73   'I'
  'J': 0b01110000, # 74   'J'
  'K': 0b01101110, # 75   'K'    Same as 'H'
  'L': 0b00011100, # 76   'L'
  'M': 0b00000000, # 77   'M'    NO DISPLAY
  'N': 0b00101010, # 78   'n'
  'O': 0b11111100, # 79   'O'
  'P': 0b11001110, # 80   'P'
  'Q': 0b11100110, # 81   'q'
  'R': 0b00001010, # 82   'r'
  'S': 0b10110110, # 83   'S'
  'T': 0b00011110, # 84   't'
  'U': 0b01111100, # 85   'U'
  'V': 0b01111100, # 86   'V'    Same as 'U'
  'W': 0b00000000, # 87   'W'    NO DISPLAY
  'X': 0b01101110, # 88   'X'    Same as 'H'
  'Y': 0b01110110, # 89   'y'
  'Z': 0b11011010, # 90   'Z'    Same as '2'
  ' ': 0b00000000, # 32   ' '    BLANK
  '-': 0b00000010, # 45   '-'    DASH
  '.': 0b00000001, # 46   '.'    DOT/COMMA
  '*': 0b11000110, # 42   '*'    STAR
  '_': 0b00010000, # 95   '_'    UNDERSCORE
}

class sevSeg():
    COMMON_CATHODE = 0
    COMMON_ANODE = 1
    NUMBERS = CHARS

    def __init__(self, digits: list, segments: list, common: int = COMMON_CATHODE, led_on_time: int = LED_ON_TIME, digit_delay: int = DIGIT_DELAY):
        """
        digits: list of pins for digits (GPIO numbers)

        segments: list of pins for segments (GPIO numbers)
        
        common: common type (0: common cathode, 1: common anode) (default: 0)

        led_on_time: time in us to keep led on (default: 5000us)

        digit_delay: time in us to delay between digits (default: 0us)
        
        NOTE: the combination of led_on_time and digit_delay define the maximum refresh rate and brightness of the display
        """

        #type error checking
        if (type(digits) != list): raise TypeError("digits must be a list")
        if (type(segments) != list): raise TypeError("segments must be a list")
        if (type(led_on_time) != int): raise TypeError("led_on_time must be an integer")
        if (type(digit_delay) != int): raise TypeError("digit_delay must be an integer")

        #input error checking
        if (len(segments) != 8): raise ValueError("segments must be a list of 8 pins")
        if (len(digits) < 1): raise ValueError("digits must be a list of at least 1 pin")
        if (led_on_time < 0): raise ValueError("led_on_time must be a positive integer")
        if (digit_delay < 0): raise ValueError("digit_delay must be a positive integer")
        if (common != self.COMMON_CATHODE and common != self.COMMON_ANODE): raise ValueError("common must be either COMMON_CATHODE or COMMON_ANODE")

        #set constants
        self.led_on_time = led_on_time
        self.digit_delay = digit_delay
        self.digits = digits #list of pins for digits as GPIO numbers
        self.segments = segments #list of pins for segments as GPIO numbers
        self.common = common #common type (0: common cathode, 1: common anode)
        
        #init digits
        self.digitsPins: list[Pin] = []
        self.digitsBin: list[int] = []
        self.digitsGPIO = GPIO
        
        for digit in self.digits:
            pin = Pin(digit, Pin.OUT) #init pin
            self.digitsPins.append(pin) #append pin to list
            pin.value(0) #reset pin value to 0
            self.digitsGPIO = self.digitsGPIO | (1 << digit) #flip corresponding bit in binary String
            self.digitsBin.append(1 << digit)
        
        #init segments
        self.segmentsPins: list[Pin] = []
        self.segmentsBin: list[int] = []
        self.segmentsGPIO = GPIO
        for segment in self.segments:
            pin = Pin(segment, Pin.OUT)
            self.segmentsPins.append(pin)
            pin.value(0)
            self.segmentsGPIO = self.segmentsGPIO | (1 << segment) #flip corresponding bit in binary String
            self.segmentsBin.append(1 << segment)
        
        #init list to set
        self.setGPIO: list[int] = []
        for digit in range(len(self.digits)):
            self.setGPIO.append(GPIO)
            
        
        
    def setDigit(self, digit: int, character: str) -> None:
        """
        Sets the digit to the specified character
        """
        # error checking
        if type(digit) != int: raise TypeError("Digit must be an integer")
        if type(character) != str: raise TypeError("Character must be a string")
        if (digit > len(self.digits) - 1): raise ValueError("Digit out of range")
        if (character not in self.NUMBERS): raise ValueError("Character not supported")
        
        #reset digit
        self.setGPIO[digit] = GPIO

        #set digit
        binLst = list('{0:08b}'.format(self.NUMBERS[str(character)]))
        for index, segment in enumerate(binLst):
            if (segment == '1'): self.setDigitSegment(digit, index)
    

    def setComma(self, digit: int) -> None:
        """
        Sets the comma on (after) the specified digit
        """
        # error checking
        if type(digit) != int: raise TypeError("Digit must be an integer")
        if (digit > len(self.digits) - 1): raise ValueError("Digit out of range")

        #set comma
        self.setDigit(digit, ".")
    
    
    def setDigitSegment(self, digit: int, segment: int) -> None:
        """
        Sets the specified segment on the specified digit
        """
        
        # error checking
        if type(digit) != int: raise TypeError("Digit must be an integer")
        if (digit > len(self.digits) - 1): raise ValueError("Digit out of range")
        if type(segment) != int: raise TypeError("Segment must be an integer")
        if (segment > len(self.segments) - 1): raise ValueError("Segment out of range")

        #set segment
        self.setGPIO[digit] = self.setGPIO[digit] | self.segmentsBin[segment]
    

    def setString(self, string: str) -> None:
        """
        Sets the display to show the specified string
        NOTE: only supports max. 4 characters plus one comma after each character
        """
        # error checking
        if type(string) != str: raise TypeError("String must be a string")

        if (len(string) > len(self.digits) * 2): raise ValueError("String too long")
        numberCommas = string.count(",") + string.count(".") #count commas and dots
        if (numberCommas > len(self.digits)): raise ValueError("Too many commas/dots")
        if (len(string) - numberCommas > len(self.digits)): raise ValueError("Too many characters")

        #insert space between double commas and before first comma and check for length errors
        if (string[0] == "," or string[0] == "."): string = " " + string
        string = string.replace(",,", ", ,").replace("..", ". .") #insert space between double commas
        if (len(string) > len(self.digits) * 2): raise ValueError("Too many double commas/dots")
        if (len(string) - numberCommas > len(self.digits)): raise ValueError("Too many characters after inserting spaces")
        

        #strip string from commas and dots
        stringClear = string.replace(",", "")
        stringClear = stringClear.replace(".", "")

        for index, character in enumerate(stringClear):
            self.setDigit(index, character)
        
        #get positions of commas and dots
        commaPos = []
        for index, character in enumerate(string):
            if (character == ","): commaPos.append(index - len(commaPos) - 1)
            if (character == "."): commaPos.append(index - len(commaPos) - 1)

        #set commas and dots
        for pos in commaPos: self.setComma(pos)
        
    

    def refreshDisplay(self) -> None:
        """
        Refreshes the display by writing the specified digits to the GPIO pin registers
        """

        # specify GPIO commands according to common type
        if (self.common == self.COMMON_CATHODE):
            GPIO_OUT_IS_SET_DIG = GPIO_OUT_CLR
            GPIO_OUT_IS_CLR_DIG = GPIO_OUT_SET
            GPIO_OUT_IS_SET_SEG = GPIO_OUT_SET
            GPIO_OUT_IS_CLR_SEG = GPIO_OUT_CLR
        elif (self.common == self.COMMON_ANODE):
            GPIO_OUT_IS_SET_DIG = GPIO_OUT_SET
            GPIO_OUT_IS_CLR_DIG = GPIO_OUT_CLR
            GPIO_OUT_IS_SET_SEG = GPIO_OUT_CLR
            GPIO_OUT_IS_CLR_SEG = GPIO_OUT_SET
        else:
            raise ValueError("Common type not supported") #should never happen -> filtered out in type checking in __init__()

        #write all digits to GPIO registers
        for digIndex, digit in enumerate(self.setGPIO):
            mem32[GPIO_SIO_ADDR + GPIO_OUT_IS_SET_DIG] = self.digitsBin[digIndex] #set current digit
            mem32[GPIO_SIO_ADDR + GPIO_OUT_IS_SET_SEG] = digit
            time.sleep_us(self.led_on_time)
            mem32[GPIO_SIO_ADDR + GPIO_OUT_IS_CLR_DIG] = self.segmentsGPIO #reset all segments
            mem32[GPIO_SIO_ADDR + GPIO_OUT_IS_CLR_SEG] = self.digitsBin[digIndex] #reset all segments
            time.sleep_us(self.digit_delay)


# testing code below
# only tested with 4 digits and 8 segments on raspberry pi pico with common cathode
# pin connections as specified here: https://github.com/jjj120/seven-segment-display-pi-pico/

if __name__ == "__main__":
    #init pins
    digits = [16, 17, 18, 19]
    segments = [15, 14, 13, 12, 11, 10, 9, 8]
    display = sevSeg(digits, segments, sevSeg.COMMON_CATHODE)
    
    display.setString("3.141")
    
    try:
        while True:
            display.refreshDisplay()
    except Exception as e:
        print(e)
    