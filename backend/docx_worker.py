"""Run layout reconstruction in a killable process with request-local files."""
import logging
import sys
logging.disable(logging.CRITICAL)
from pdf2docx import Converter

if __name__ == "__main__":
    converter = Converter(sys.argv[1])
    try:
        converter.convert(sys.argv[2], multi_processing=False)
    finally:
        converter.close()
