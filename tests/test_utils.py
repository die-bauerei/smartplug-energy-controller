import logging
import sys
import unittest

from smartplug_energy_controller.utils import *

logging.basicConfig(stream=sys.stdout, level=logging.ERROR)
logger = logging.getLogger(__name__)


class TestRollingValues(unittest.TestCase):

    def test_add(self) -> None:
        rolling_values = RollingValues(timedelta(minutes=10))
        self.assertEqual(len(rolling_values), 0)
        now = datetime.now()
        for i in range(10):
            rolling_values.add(ValueEntry(i, now + i*timedelta(seconds=61)))
            self.assertEqual(len(rolling_values), i+1)
            self.assertEqual(i, rolling_values[i].value)
        
        self.assertEqual(len(rolling_values), 10)

        # value count should stay at 10 because the next value extends the window_time_delta
        rolling_values.add(ValueEntry(99, now + 10*timedelta(seconds=61)))
        self.assertEqual(len(rolling_values), 10)
        self.assertEqual(99, rolling_values[len(rolling_values)-1].value)
        self.assertEqual(1, rolling_values[0].value)

        # check the case when the value count changes (e.g. one is being added but three deleted)
        rolling_values.add(ValueEntry(100, now + 13*timedelta(seconds=61)))
        self.assertEqual(len(rolling_values), 8)
        self.assertEqual(100, rolling_values[len(rolling_values)-1].value)
        self.assertEqual(4, rolling_values[0].value)

        # Timestamps must be in ascending order 
        with self.assertRaises(AssertionError):
            rolling_values.add(ValueEntry(99, now + 9*timedelta(seconds=61)))
        
    def test_ratio(self) -> None:
        rolling_values = RollingValues(timedelta(minutes=10))
        with self.assertRaises(AssertionError):
            rolling_values.ratio(10)
        now = datetime.now()
        rolling_values.add(ValueEntry(0, now))
        with self.assertRaises(AssertionError):
            rolling_values.ratio(10)
        rolling_values.add(ValueEntry(0, now + timedelta(minutes=1)))
        ratio=rolling_values.ratio(10)
        self.assertEqual(ratio.threshold_value, 10)
        self.assertEqual(ratio.less_threshold_ratio, 1)
        rolling_values.add(ValueEntry(100, now + timedelta(minutes=2)))
        ratio=rolling_values.ratio(10)
        self.assertEqual(ratio.less_threshold_ratio, 1/2)
        rolling_values.add(ValueEntry(110, now + timedelta(seconds=150)))
        ratio=rolling_values.ratio(10)
        self.assertEqual(ratio.less_threshold_ratio, 2/5)
        rolling_values.add(ValueEntry(0, now + timedelta(minutes=3)))
        ratio=rolling_values.ratio(10)
        self.assertEqual(ratio.less_threshold_ratio, 3/6)
        rolling_values.add(ValueEntry(120, now + timedelta(minutes=3, seconds=30)))
        ratio=rolling_values.ratio(10)
        self.assertEqual(ratio.less_threshold_ratio, 3/7)

if __name__ == '__main__':
    try:
        unittest.main()
    except Exception as e:
        logger.exception("Caught Exception: " + str(e))
    except:
        logger.exception("Caught unknow exception")