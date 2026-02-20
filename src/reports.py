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
            'active': self._report_active_notams,
            'closures': self._report_closures,
            'drone': self._report_drone_notams,
            'stats': self._report_statistics,
            'by-airport': self._report_by_airport,
            'priority': self._report_priority,
            'search-term': self._report_by_search_term
        }
        
        if report_name not in reports:
            print(f"Unknown report: {report_name}")
            print(f"Available reports: {', '.join(reports.keys())}")
            sys.exit(1)
        
        reports[report_name]()
    
    def _report_active_notams(self) -> None:
        """Display all active NOTAMs."""
        print("\n=== Active NOTAMs (score >= 30) ===\n")
        results = self.db.get_active_notams(min_score=30)
        
        if results:
            display_results = []
            for r in results:
                display_results.append({
                    'ID': r['notam_id'][:12],
                    'Airport': r['airport_code'] or r['location'] or 'N/A',
                    'Score': r['priority_score'],
                    'Type': r['notam_type'] or 'N',
                    'Drone': '✓' if r['is_drone_related'] else '',
                    'Closure': '✓' if r['is_closure'] else '',
                    'Valid To': r['valid_to'][:10] if r['valid_to'] else 'PERM',
                })
            self._display_results(display_results)
        else:
            print("No active NOTAMs found.\n")
    
    def _report_closures(self) -> None:
        """Display closure NOTAMs."""
        print("\n=== Active Closures ===\n")
        results = self.db.get_closures(active_only=True)
        
        if results:
            display_results = []
            for r in results:
                display_results.append({
                    'ID': r['notam_id'][:12],
                    'Airport': r['airport_code'] or r['location'] or 'N/A',
                    'Score': r['priority_score'],
                    'Drone': '✓' if r['is_drone_related'] else '',
                    'Reason': r['body'][:60] if r['body'] else 'N/A',
                })
            self._display_results(display_results)
        else:
            print("No active closures found.\n")
    
    def _report_drone_notams(self) -> None:
        """Display drone-related NOTAMs."""
        print("\n=== Drone-Related NOTAMs ===\n")
        results = self.db.get_drone_notams(active_only=True)
        
        if results:
            display_results = []
            for r in results:
                display_results.append({
                    'ID': r['notam_id'][:12],
                    'Airport': r['airport_code'] or r['location'] or 'N/A',
                    'Score': r['priority_score'],
                    'Search Term': r['search_term'] or 'N/A',
                    'Body': r['body'][:60] if r['body'] else 'N/A',
                })
            self._display_results(display_results)
        else:
            print("No drone-related NOTAMs found.\n")
    
    def _report_priority(self) -> None:
        """Display high priority NOTAMs."""
        print("\n=== High Priority NOTAMs (score >= 50) ===\n")
        results = self.db.get_active_notams(min_score=50)
        
        if results:
            display_results = []
            for r in results:
                display_results.append({
                    'ID': r['notam_id'],
                    'Airport': r['airport_code'] or r['location'] or 'N/A',
                    'Score': r['priority_score'],
                    'Type': r['notam_type'] or 'N',
                    'Closure': '✓' if r['is_closure'] else '',
                    'Drone': '✓' if r['is_drone_related'] else '',
                })
            self._display_results(display_results)
        else:
            print("No high priority NOTAMs found.\n")
    
    def _report_by_search_term(self) -> None:
        """Prompt for search term and display results."""
        print("\n=== NOTAMs by Search Term ===\n")
        
        # Get unique search terms from DB
        query = "SELECT DISTINCT search_term FROM notams WHERE search_term IS NOT NULL ORDER BY search_term"
        terms = self.db.execute_custom_query(query)
        
        if not terms:
            print("No search terms found in database.")
            return
        
        print("Available search terms:")
        for i, row in enumerate(terms, 1):
            print(f"  {i}. {row['search_term']}")
        
        try:
            choice = input("\nEnter number or search term: ").strip()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(terms):
                    term = terms[idx]['search_term']
                else:
                    print("Invalid choice")
                    return
            else:
                term = choice
            
            results = self.db.get_by_search_term(term)
            
            if results:
                display_results = []
                for r in results:
                    display_results.append({
                        'ID': r['notam_id'],
                        'Airport': r['airport_code'] or r['location'] or 'N/A',
                        'Score': r['priority_score'],
                        'Active': '✓' if (r['valid_to'] is None or r['valid_to'] > datetime.now().isoformat()) else '',
                        'Body': r['body'][:60] if r['body'] else 'N/A',
                    })
                self._display_results(display_results)
            else:
                print(f"No NOTAMs found for term: {term}\n")
                
        except KeyboardInterrupt:
            print("\nCancelled")
            sys.exit(0)
    
    def _report_statistics(self) -> None:
        """Display summary statistics."""
        print("\n=== NOTAM Statistics ===\n")
        stats = self.db.get_statistics()
        
        print(f"Total NOTAMs in database: {stats['total_notams']}")
        print(f"Active NOTAMs: {stats['active_notams']}")
        print(f"Closures (all time): {stats['closures']}")
        print(f"Active closures: {stats['active_closures']}")
        print(f"Drone-related (all time): {stats['drone_notams']}")
        print(f"Active drone-related: {stats['active_drone_notams']}")
        print(f"High priority (score >= 80): {stats['high_priority']}")
        
        if stats['total_notams'] > 0:
            drone_pct = (stats['drone_notams'] / stats['total_notams']) * 100
            closure_pct = (stats['closures'] / stats['total_notams']) * 100
            print(f"\nDrone NOTAM percentage: {drone_pct:.1f}%")
            print(f"Closure percentage: {closure_pct:.1f}%")
        
        print()
    
    def _report_by_airport(self) -> None:
        """Display NOTAMs grouped by airport."""
        print("\n=== NOTAMs by Airport ===\n")
        
        query = """
        SELECT 
            airport_code,
            MAX(airport_name) as airport_name,
            COUNT(*) as total_notams,
            SUM(CASE WHEN is_drone_related = 1 THEN 1 ELSE 0 END) as drone_notams,
            SUM(CASE WHEN is_closure = 1 THEN 1 ELSE 0 END) as closures,
            SUM(CASE WHEN (valid_to IS NULL OR valid_to > datetime('now')) 
                      AND (notam_type != 'CANCEL' OR notam_type IS NULL)
                 THEN 1 ELSE 0 END) as active_notams
        FROM notams
        WHERE airport_code IS NOT NULL
        GROUP BY airport_code
        ORDER BY total_notams DESC
        LIMIT 50
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
        print("  active       - Show active NOTAMs (score >= 30)")
        print("  closures     - Show active closures")
        print("  drone        - Show drone-related NOTAMs")
        print("  stats        - Show summary statistics")
        print("  by-airport   - Show NOTAMs grouped by airport")
        print("  priority     - Show high priority NOTAMs (score >= 50)")
        print("  search-term  - Show NOTAMs by search term")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'query' and len(sys.argv) >= 3:
        runner.run_query_file(sys.argv[2])
    else:
        runner.run_predefined_report(command)


if __name__ == '__main__':
    main()