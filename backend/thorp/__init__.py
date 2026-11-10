

# a list row can be a whole stamped book (Ogden v0.1.1 carries every text inline), which is far past
# csv's default 131,072-byte field cap (9 November)
import csv as _csv
import sys as _sys

_csv.field_size_limit(min(_sys.maxsize, 10**8))
