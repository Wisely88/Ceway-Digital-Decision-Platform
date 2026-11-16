import unittest
from engine.historical_high_zone_audit import audit, distribution, binomial_upper, validate

class HistoricalHighZoneAuditTests(unittest.TestCase):
    def test_distribution_normalized(self):
        self.assertAlmostEqual(sum(distribution(7)), 1.0)
        self.assertAlmostEqual(sum(k*p for k,p in enumerate(distribution(7))), 1.0)
    def test_tail(self):
        self.assertAlmostEqual(binomial_upper(3,2,0.5),0.5)
        self.assertEqual(binomial_upper(3,4,0.5),0.0)
    def test_reject_duplicates(self):
        row=dict(issue="7001",f1="1",f2="2",f3="3",f4="4",f5="29",b1="1",b2="2")
        with self.assertRaises(ValueError):
            validate([row,row])
    def test_audit(self):
        row=dict(issue="7001",f1="1",f2="29",f3="30",f4="31",f5="35",b1="1",b2="2")
        result=audit([row])
        self.assertEqual(result["observed_total"],4)
        self.assertEqual(result["observed_at_least_three"],1)

if __name__=="__main__":
    unittest.main()
