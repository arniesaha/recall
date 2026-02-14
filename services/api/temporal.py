"""
Temporal expression parser for Recall search.

Extracts date ranges from natural language queries like:
- "this week" → current week
- "last month" → previous month
- "yesterday" → yesterday's date
- "in January" → January of current/recent year
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class DateRange:
    """A date range for filtering search results."""
    start: str  # YYYY-MM-DD format
    end: str    # YYYY-MM-DD format
    expression: str  # Original expression matched
    
    def __repr__(self):
        return f"DateRange({self.start} to {self.end}, expr='{self.expression}')"


# Month name mappings
MONTHS = {
    'january': 1, 'jan': 1,
    'february': 2, 'feb': 2,
    'march': 3, 'mar': 3,
    'april': 4, 'apr': 4,
    'may': 5,
    'june': 6, 'jun': 6,
    'july': 7, 'jul': 7,
    'august': 8, 'aug': 8,
    'september': 9, 'sep': 9, 'sept': 9,
    'october': 10, 'oct': 10,
    'november': 11, 'nov': 11,
    'december': 12, 'dec': 12,
}

# Day of week mappings (0 = Monday)
DAYS_OF_WEEK = {
    'monday': 0, 'mon': 0,
    'tuesday': 1, 'tue': 1, 'tues': 1,
    'wednesday': 2, 'wed': 2,
    'thursday': 3, 'thu': 3, 'thurs': 3,
    'friday': 4, 'fri': 4,
    'saturday': 5, 'sat': 5,
    'sunday': 6, 'sun': 6,
}


def parse_temporal_expression(query: str, reference_date: Optional[datetime] = None) -> Optional[DateRange]:
    """
    Parse temporal expressions from a query string.
    
    Args:
        query: The search query
        reference_date: Reference date for relative expressions (defaults to now)
    
    Returns:
        DateRange if temporal expression found, None otherwise
    """
    if reference_date is None:
        reference_date = datetime.now()
    
    query_lower = query.lower()
    
    # Today
    if re.search(r'\btoday\b', query_lower):
        date_str = reference_date.strftime('%Y-%m-%d')
        return DateRange(date_str, date_str, 'today')
    
    # Yesterday
    if re.search(r'\byesterday\b', query_lower):
        yesterday = reference_date - timedelta(days=1)
        date_str = yesterday.strftime('%Y-%m-%d')
        return DateRange(date_str, date_str, 'yesterday')
    
    # This week (Monday to today)
    if re.search(r'\bthis week\b', query_lower):
        # Get Monday of current week
        days_since_monday = reference_date.weekday()
        monday = reference_date - timedelta(days=days_since_monday)
        return DateRange(
            monday.strftime('%Y-%m-%d'),
            reference_date.strftime('%Y-%m-%d'),
            'this week'
        )
    
    # Last week
    if re.search(r'\blast week\b', query_lower):
        days_since_monday = reference_date.weekday()
        this_monday = reference_date - timedelta(days=days_since_monday)
        last_monday = this_monday - timedelta(days=7)
        last_sunday = this_monday - timedelta(days=1)
        return DateRange(
            last_monday.strftime('%Y-%m-%d'),
            last_sunday.strftime('%Y-%m-%d'),
            'last week'
        )
    
    # Past N days / last N days
    match = re.search(r'\b(?:past|last)\s+(\d+)\s+days?\b', query_lower)
    if match:
        days = int(match.group(1))
        start = reference_date - timedelta(days=days)
        return DateRange(
            start.strftime('%Y-%m-%d'),
            reference_date.strftime('%Y-%m-%d'),
            f'last {days} days'
        )
    
    # This month
    if re.search(r'\bthis month\b', query_lower):
        first_of_month = reference_date.replace(day=1)
        return DateRange(
            first_of_month.strftime('%Y-%m-%d'),
            reference_date.strftime('%Y-%m-%d'),
            'this month'
        )
    
    # Last month
    if re.search(r'\blast month\b', query_lower):
        first_of_this_month = reference_date.replace(day=1)
        last_of_prev_month = first_of_this_month - timedelta(days=1)
        first_of_prev_month = last_of_prev_month.replace(day=1)
        return DateRange(
            first_of_prev_month.strftime('%Y-%m-%d'),
            last_of_prev_month.strftime('%Y-%m-%d'),
            'last month'
        )
    
    # Specific month name (e.g., "in January", "January meetings")
    for month_name, month_num in MONTHS.items():
        pattern = rf'\b{month_name}\b'
        if re.search(pattern, query_lower):
            # Determine year - use current year, or previous year if month is in future
            year = reference_date.year
            if month_num > reference_date.month:
                year -= 1
            
            # Get first and last day of that month
            first_of_month = datetime(year, month_num, 1)
            if month_num == 12:
                last_of_month = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                last_of_month = datetime(year, month_num + 1, 1) - timedelta(days=1)
            
            return DateRange(
                first_of_month.strftime('%Y-%m-%d'),
                last_of_month.strftime('%Y-%m-%d'),
                month_name
            )
    
    # Last Monday/Tuesday/etc.
    for day_name, day_num in DAYS_OF_WEEK.items():
        pattern = rf'\blast\s+{day_name}\b'
        if re.search(pattern, query_lower):
            days_ago = (reference_date.weekday() - day_num) % 7
            if days_ago == 0:
                days_ago = 7  # "last Monday" when today is Monday means 7 days ago
            target_date = reference_date - timedelta(days=days_ago)
            date_str = target_date.strftime('%Y-%m-%d')
            return DateRange(date_str, date_str, f'last {day_name}')
    
    # On Monday/Tuesday/etc. (most recent occurrence)
    for day_name, day_num in DAYS_OF_WEEK.items():
        pattern = rf'\bon\s+{day_name}\b'
        if re.search(pattern, query_lower):
            days_ago = (reference_date.weekday() - day_num) % 7
            target_date = reference_date - timedelta(days=days_ago)
            date_str = target_date.strftime('%Y-%m-%d')
            return DateRange(date_str, date_str, f'on {day_name}')
    
    # Specific date patterns: "Feb 10", "February 10", "10 Feb", "2026-02-10"
    # ISO format: YYYY-MM-DD
    match = re.search(r'\b(\d{4})-(\d{2})-(\d{2})\b', query_lower)
    if match:
        date_str = match.group(0)
        return DateRange(date_str, date_str, date_str)
    
    # "Feb 10" or "February 10"
    for month_name, month_num in MONTHS.items():
        pattern = rf'\b{month_name}\s+(\d{{1,2}})\b'
        match = re.search(pattern, query_lower)
        if match:
            day = int(match.group(1))
            year = reference_date.year
            # If the date is in the future, assume last year
            try:
                target_date = datetime(year, month_num, day)
                if target_date > reference_date:
                    target_date = datetime(year - 1, month_num, day)
                date_str = target_date.strftime('%Y-%m-%d')
                return DateRange(date_str, date_str, f'{month_name} {day}')
            except ValueError:
                pass  # Invalid date
    
    return None


def extract_query_without_temporal(query: str, date_range: Optional[DateRange]) -> str:
    """
    Remove the temporal expression from a query to get cleaner search terms.
    
    Args:
        query: Original query
        date_range: Parsed date range (contains the matched expression)
    
    Returns:
        Query with temporal expression removed
    """
    if date_range is None:
        return query
    
    # Remove common temporal phrases
    cleaned = query
    
    # Patterns to remove (order matters - longer patterns first)
    patterns_to_remove = [
        r'\bfrom\s+this\s+week\b',
        r'\bthis\s+week\b',
        r'\blast\s+week\b',
        r'\bthis\s+month\b',
        r'\blast\s+month\b',
        r'\btoday\b',
        r'\byesterday\b',
        r'\b(?:past|last)\s+\d+\s+days?\b',
        r'\blast\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
        r'\bon\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
        r'\bin\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)(?:\s+\d{4})?\b',
        r'\bfrom\s+(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)(?:\s+\d{4})?\b',
        r'\b(?:january|february|march|april|may|june|july|august|september|october|november|december)(?:\s+\d{4})?\b',
        r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)(?:\s+\d{4})?\b',
        r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\s+\d{1,2}(?:,?\s+\d{4})?\b',
        r'\b\d{4}-\d{2}-\d{2}\b',
    ]
    
    for pattern in patterns_to_remove:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Clean up extra whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned


# Quick test
if __name__ == "__main__":
    test_queries = [
        "What are the key highlights from all my meetings this week?",
        "meetings with Vijay last month",
        "what did we discuss yesterday",
        "notes from last Monday",
        "January performance reviews",
        "past 7 days action items",
        "meetings in February",
        "what happened on Tuesday",
        "this month's 1:1s",
    ]
    
    print(f"Reference date: {datetime.now().strftime('%Y-%m-%d')}\n")
    
    for q in test_queries:
        result = parse_temporal_expression(q)
        cleaned = extract_query_without_temporal(q, result)
        print(f"Query: {q}")
        print(f"  Range: {result}")
        print(f"  Cleaned: {cleaned}")
        print()
