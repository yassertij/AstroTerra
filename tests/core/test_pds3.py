import pytest

from paf_core.errors import LabelParseError
from paf_core.pds3 import Quantity, parse_label_text

LABEL = """PDS_VERSION_ID = PDS3
/* comment line */
^IMAGE = "MEGT00N090HB.IMG"
DATA_SET_ID = "MGS-M-MOLA-5-MEGDR-L3-V1.0"
RECORD_BYTES = 23040
DESCRIPTION = "first line
   second   line"
OBJECT = IMAGE
  LINES = 5632
  SAMPLE_TYPE = MSB_INTEGER
END_OBJECT = IMAGE
OBJECT = IMAGE_MAP_PROJECTION
  A_AXIS_RADIUS = 3396.0 <KM>
  MAP_SCALE = 0.463 <KM/PIXEL>
  LINE_PROJECTION_OFFSET = 0.5
END_OBJECT = IMAGE_MAP_PROJECTION
END
"""


def test_parses_values_units_objects():
    lbl = parse_label_text(LABEL)
    assert lbl["^IMAGE"] == "MEGT00N090HB.IMG"
    assert lbl["DATA_SET_ID"] == "MGS-M-MOLA-5-MEGDR-L3-V1.0"
    assert lbl["RECORD_BYTES"] == 23040
    assert lbl["DESCRIPTION"] == "first line second line"
    assert lbl["IMAGE"]["LINES"] == 5632
    assert lbl["IMAGE"]["SAMPLE_TYPE"] == "MSB_INTEGER"
    assert lbl.find("A_AXIS_RADIUS") == Quantity(3396.0, "KM")
    assert lbl.find("MAP_SCALE") == Quantity(0.463, "KM/PIXEL")
    assert lbl.find("LINE_PROJECTION_OFFSET") == 0.5


def test_unbalanced_object_rejected():
    with pytest.raises(LabelParseError):
        parse_label_text("OBJECT = IMAGE\nLINES = 1\nEND\n")


def test_unterminated_string_rejected():
    with pytest.raises(LabelParseError):
        parse_label_text('DESCRIPTION = "never closed\nEND\n')


def test_garbage_line_rejected():
    with pytest.raises(LabelParseError):
        parse_label_text("this is not a label\n")
