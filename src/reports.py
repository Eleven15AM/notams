"""Reports module for running custom queries."""
import sys
import os
from pathlib import Path
from src.database import NotamDatabase
from src.config import Config
from datetime import datetime


class ReportRunner:
    """Handles custom report execution."""
    
    def __init__(self):
        self.db = NotamDatabase(Config.DATABASE_PATH)
    
    def run_query_file(self, query_file: str) -> None:
        """
        Execute a SQL query from a file and display results.
        
        Args:
            query_file: Path to SQL file
        """
        query_path = Path(query_file)
        
        if not query_path.exists():
            print(f"Error: Query file not found: {query_file}")
            sys.exit(1)
        
        with open(query_path, 'r') as f:
            query = f.read()
        
        print(f"\n=== Executing query from {query_file} ===\n")
        print(f"Query:\n{query}\n")
        
        try:
            results = self.db.execute_custom_query(query)
            self._display_results(results)
        except Exception as e:
            print(f"Error executing query: {e}")
            sys.exit(1)
    
    def _display_results(self, results: list) -> None:
        """Display query results in a formatted table."""
        if not results:
            print("No results found.")
            return
        
        # Get column names
        columns = list(results[0].keys())
        
        # Calculate column widths
        widths = {col: len(col) for col in columns}
        for row in results:
            for col in columns:
                val_len = len(str(row[col]))
                if val_len > widths[col]:
                    widths[col] = min(val_len, 100)  # Cap at 100 chars
        
        # Print header
        header = " | ".join(col.ljust(widths[col]) for col in columns)
        separator = "-+-".join("-" * widths[col] for col in columns)
        
        print(header)
        print(separator)
        
        # Print rows
        for row in results:
            print(" | ".join(str(row[col])[:widths[col]].ljust(widths[col]) for col in columns))
        
        print(f"\n{len(results)} row(s) returned.\n")
    
    def run_predefined_report(self, report_name: str) -> None:
        """Run a predefined report."""
        reports = {
            'active': self._report_active_closures,
            'today': self._report_todays_closures,
            'drone': self._report_drone_closures,
            'stats': self._report_statistics,
            'by-airport': self._report_by_airport
        }
        
        if report_name not in reports:
            print(f"Unknown report: {report_name}")
            print(f"Available reports: {', '.join(reports.keys())}")
            sys.exit(1)
        
        reports[report_name]()
    
    def _report_active_closures(self) -> None:
        """Display all active closures."""
        print("\n=== Active Airport Closures ===\n")
        results = self.db.get_active_closures()
        
        if results:
            # Simplify display - show most important fields
            display_results = []
            for r in results:
                display_results.append({
                    'NOTAM ID': r['notam_id'],
                    'Airport': f"{r['airport_code']} ({r.get('airport_name', 'N/A')})",
                    'Start': r['closure_start'][:16] if r['closure_start'] else 'N/A',
                    'End': r['closure_end'][:16] if r['closure_end'] else 'PERM',
                    'Drone': '  YES' if r['is_drone_related'] else 'No',
                    'Weight': r['weight'],
                    'Reason': r['reason'][:60]
                })
            self._display_results(display_results)
        else:
            print("No active closures found.\n")
    
    def _report_todays_closures(self) -> None:
        """Display closures for today."""
        print(f"\n=== Today's Airport Closures ({datetime.now().strftime('%Y-%m-%d')}) ===\n")
        results = self.db.get_todays_closures()
        
        if results:
            display_results = []
            for r in results:
                display_results.append({
                    'NOTAM ID': r['notam_id'],
                    'Airport': f"{r['airport_code']} ({r.get('airport_name', 'N/A')})",
                    'Start': r['closure_start'][:16] if r['closure_start'] else 'N/A',
                    'End': r['closure_end'][:16] if r['closure_end'] else 'PERM',
                    'Drone': '  YES' if r['is_drone_related'] else 'No',
                    'Reason': r['reason'][:60]
                })
            self._display_results(display_results)
        else:
            print("No closures for today.\n")
    
    def _report_drone_closures(self) -> None:
        """Display drone-related closures."""
        print("\n=== Drone-Related Closures ===\n")
        results = self.db.get_drone_closures()
        
        if results:
            display_results = []
            for r in results:
                display_results.append({
                    'NOTAM ID': r['notam_id'],
                    'Airport': f"{r['airport_code']} ({r.get('airport_name', 'N/A')})",
                    'Issued': r['issue_date'][:10] if r['issue_date'] else 'N/A',
                    'Start': r['closure_start'][:16] if r['closure_start'] else 'N/A',
                    'End': r['closure_end'][:16] if r['closure_end'] else 'PERM',
                    'Reason': r['reason'][:60]
                })
            self._display_results(display_results)
        else:
            print("No drone-related closures found.\n")
    
    def _report_statistics(self) -> None:
        """Display summary statistics."""
        print("\n=== NOTAM Statistics ===\n")
        stats = self.db.get_statistics()
        
        print(f"Total closures in database: {stats['total_closures']}")
        print(f"Active closures: {stats['active_closures']}")
        print(f"Today's closures: {stats['todays_closures']}")
        print(f"Drone-related (all time): {stats['drone_closures']}")
        print(f"Drone-related (active): {stats['active_drone_closures']}")
        
        if stats['total_closures'] > 0:
            drone_pct = (stats['drone_closures'] / stats['total_closures']) * 100
            print(f"Drone closure percentage: {drone_pct:.1f}%")
        
        print()
    
    def _report_by_airport(self) -> None:
        """Display closures grouped by airport."""
        print("\n=== Closures by Airport ===\n")
        
        query = """
        SELECT 
            airport_code,
            MAX(airport_name) as airport_name,
            COUNT(*) as total_closures,
            SUM(CASE WHEN is_drone_related = 1 THEN 1 ELSE 0 END) as drone_closures,
            SUM(CASE WHEN closure_end IS NULL OR closure_end > datetime('now') THEN 1 ELSE 0 END) as active_closures
        FROM airport_closures
        GROUP BY airport_code
        ORDER BY total_closures DESC
        """
        
        results = self.db.execute_custom_query(query)
        self._display_results(results)


def main():
    """Main entry point for report runner."""
    runner = ReportRunner()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m src.reports <report_name>")
        print("  python -m src.reports query <query_file>")
        print("\nAvailable reports:")
        print("  active       - Show all active closures")
        print("  today        - Show today's closures")
        print("  drone        - Show drone-related closures")
        print("  stats        - Show summary statistics")
        print("  by-airport   - Show closures grouped by airport")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'query' and len(sys.argv) >= 3:
        runner.run_query_file(sys.argv[2])
    else:
        runner.run_predefined_report(command)


if __name__ == '__main__':
    main()