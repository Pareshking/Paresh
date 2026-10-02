#!/usr/bin/env python3
"""
NSE Index Historical Data Anomaly Analysis
Detailed analysis of constituent count anomalies and validation rules
"""

import csv
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import json

class IndexAnalyzer:
    def __init__(self, csv_file, expected_constituents):
        self.csv_file = Path(csv_file)
        self.expected_constituents = expected_constituents
        self.data = self._load_data()
        self.anomalies = []
        self.snapshots = {}
        self.analyze()

    def _load_data(self):
        """Load CSV data"""
        data = []
        with open(self.csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append({
                    'date': row['Effective_Date'],
                    'symbol': row['Symbol']
                })
        return data

    def analyze(self):
        """Perform analysis"""
        # Count constituents per date
        date_symbols = defaultdict(list)
        for item in self.data:
            date_symbols[item['date']].append(item['symbol'])

        self.snapshots = {
            date: symbols for date, symbols in sorted(date_symbols.items())
        }

        # Find anomalies
        for date, symbols in self.snapshots.items():
            count = len(symbols)
            if count != self.expected_constituents:
                deviation = count - self.expected_constituents
                deviation_pct = (deviation / self.expected_constituents) * 100
                self.anomalies.append({
                    'date': date,
                    'count': count,
                    'expected': self.expected_constituents,
                    'deviation': deviation,
                    'deviation_pct': deviation_pct
                })

    def print_summary(self):
        """Print summary statistics"""
        print(f"\n{'='*80}")
        print(f"Index: {self.csv_file.stem}")
        print(f"Expected Constituents: {self.expected_constituents}")
        print(f"Total Snapshots: {len(self.snapshots)}")
        print(f"Total Rows: {len(self.data)}")
        unique = len(set(item['symbol'] for item in self.data))
        print(f"Unique Symbols: {unique}")
        print(f"{'='*80}\n")

        counts = [len(syms) for syms in self.snapshots.values()]
        print(f"Constituent Count Statistics:")
        print(f"  Min: {min(counts)}")
        print(f"  Max: {max(counts)}")
        print(f"  Average: {sum(counts)/len(counts):.1f}")
        print(f"  Mode: {max(set(counts), key=counts.count)}")
        print(f"  Snapshots with exact count: {sum(1 for c in counts if c == self.expected_constituents)}/{len(counts)}")

    def print_anomalies(self, top_n=20):
        """Print anomalies sorted by deviation"""
        if not self.anomalies:
            print("\n✓ No anomalies detected!")
            return

        print(f"\n{'='*80}")
        print(f"ANOMALIES (sorted by absolute deviation)")
        print(f"{'='*80}\n")

        sorted_anomalies = sorted(self.anomalies, key=lambda x: abs(x['deviation']), reverse=True)

        header = (
            f"{'Date':<12} {'Count':<8} {'Expected':<8} {'Deviation':<12} "
            f"{'% Dev':<8} {'Status':<20}"
        )
        print(header)
        print("-" * 80)

        for anom in sorted_anomalies[:top_n]:
            dev = abs(anom['deviation'])
            if dev > 50:
                status = "⚠️  CRITICAL"
            elif dev > 20:
                status = "⚠️  MAJOR"
            else:
                status = "⚠️  MINOR"
            print(
                f"{anom['date']:<12} {anom['count']:<8} {anom['expected']:<8} "
                f"{anom['deviation']:>+11} {anom['deviation_pct']:>+6.1f}% {status:<20}"
            )

        if len(self.anomalies) > top_n:
            print(f"\n... and {len(self.anomalies) - top_n} more anomalies")

    def get_date_range(self):
        """Get date range"""
        dates = sorted(self.snapshots.keys())
        return dates[0], dates[-1]

    def get_constitution_on_date(self, date):
        """Get constituents on a specific date"""
        return self.snapshots.get(date, [])

    def find_symbol_history(self, symbol):
        """Find all dates a symbol appears"""
        dates = []
        for date, symbols in self.snapshots.items():
            if symbol in symbols:
                dates.append(date)
        return dates

    def to_dict(self):
        """Export analysis as dict"""
        unique = len(set(item['symbol'] for item in self.data))
        return {
            'index': self.csv_file.stem,
            'expected_constituents': self.expected_constituents,
            'total_snapshots': len(self.snapshots),
            'total_rows': len(self.data),
            'unique_symbols': unique,
            'date_range': self.get_date_range(),
            'anomalies_count': len(self.anomalies),
            'anomalies': self.anomalies
        }


def main():
    data_dir = Path(__file__).parent.parent / 'data'

    indices = [
        (data_dir / 'NIFTY_MIDCAP_150.csv', 150),
        (data_dir / 'NIFTY_SMALLCAP_250.csv', 250),
        (data_dir / 'NIFTY_MICROCAP_250.csv', 250),
    ]

    analyzers = []

    for csv_file, expected in indices:
        if csv_file.exists():
            print(f"\n📊 Analyzing {csv_file.name}...")
            analyzer = IndexAnalyzer(csv_file, expected)
            analyzers.append(analyzer)
            analyzer.print_summary()
            analyzer.print_anomalies(top_n=15)
        else:
            print(f"⚠️  File not found: {csv_file}")

    # Save detailed report
    print(f"\n{'='*80}")
    print("SAVING DETAILED ANALYSIS...")
    print(f"{'='*80}\n")

    report = {
        'analysis_date': datetime.now().isoformat(),
        'indices': [a.to_dict() for a in analyzers]
    }

    report_file = Path(__file__).parent.parent / 'reports' / 'anomaly_analysis.json'
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"✓ Detailed report saved to: {report_file}")

    # Symbol stability analysis
    print(f"\n{'='*80}")
    print("SYMBOL STABILITY ANALYSIS")
    print(f"{'='*80}\n")

    for analyzer in analyzers:
        print(f"\n{analyzer.csv_file.stem}:")
        all_symbols = set(item['symbol'] for item in analyzer.data)
        stable = sum(
            1 for s in all_symbols
            if len(analyzer.find_symbol_history(s)) == len(analyzer.snapshots)
        )
        print(f"  Total unique symbols: {len(all_symbols)}")
        print(f"  Always present (all snapshots): {stable}")
        changed = len(all_symbols) - stable
        print(f"  Changed at least once: {changed}")


if __name__ == '__main__':
    main()
