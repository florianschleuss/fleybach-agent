from unittest import TestLoader, TextTestRunner, TestSuite
from deviceTest import TestDevice
from reasonTest import TestReasonFlow
from utilsTest import TestLocalDevice, TestPowerSwitchable, TestRemoteDevice, TestSwitchable  # noqa


if __name__ == "__main__":

    loader = TestLoader()
    tests = [TestSwitchable,
             TestPowerSwitchable,
             TestLocalDevice,
             TestRemoteDevice,
             TestDevice,
             TestReasonFlow
             ]
    suite = TestSuite(loader.loadTestsFromTestCase(test)
                      for test in (tests))

    runner = TextTestRunner(verbosity=2)
    runner.run(suite)
