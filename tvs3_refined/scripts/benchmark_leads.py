import sys
import os
import time
import statistics
import pandas as pd

# Add the parent directory to sys.path to allow importing tvs3_refined modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
import charts

def print_section(title):
    print("=" * 65)
    print(f" {title.upper()} ".center(65, "="))
    print("=" * 65)

def run_benchmark(label, func, *args, iterations=20, **kwargs):
    print(f"Running '{label}' benchmark over {iterations} iterations...")
    times = []
    
    # Warmup run (discarded)
    try:
        func(*args, **kwargs)
    except Exception as e:
        print(f"  Warmup failed: {e}")
        return None

    for _ in range(iterations):
        t_start = time.perf_counter()
        func(*args, **kwargs)
        t_end = time.perf_counter()
        times.append((t_end - t_start) * 1000) # Convert to ms
        
    mean_t = statistics.mean(times)
    min_t = min(times)
    max_t = max(times)
    stdev_t = statistics.stdev(times) if len(times) > 1 else 0.0
    
    print(f"  Completed. Avg: {mean_t:.2f}ms | Min: {min_t:.2f}ms | Max: {max_t:.2f}ms | Stdev: {stdev_t:.2f}ms")
    return {
        "label": label,
        "mean": mean_t,
        "min": min_t,
        "max": max_t,
        "stdev": stdev_t,
        "raw_times": times
    }

def main():
    print_section("MyTVS Dashboard Performance Benchmark")
    
    # 1. Measure DB Load Speed
    db_results = run_benchmark("Database Ingestion Query (db.get_data)", db.get_data, iterations=5)
    if not db_results:
        print("Failed to run database ingestion benchmark.")
        return
        
    df = db.get_data()
    print(f"Active dataset size: {len(df):,} rows, {df.shape[1]} columns.\n")
    
    # Map stages for pipeline functions
    df_stage = charts._map_stages(df)
    
    # 2. Benchmark specific Leads/Pipeline metrics rendering
    leads_kpi = run_benchmark("Leads KPI Bar (_lt_kpi_bar)", charts._lt_kpi_bar, df, iterations=20)
    leads_pivot = run_benchmark("Leads Summary Pivot Table (build_lead_pivot - Category)", charts.build_lead_pivot, df, 'category', iterations=20)
    leads_pivot_detail = run_benchmark("Leads Detailed Pivot (build_lead_pivot - Product Detailed)", charts.build_lead_pivot, df, 'category', show_subcategories=True, iterations=20)
    leads_nonconv = run_benchmark("Non-Conversion Table (build_nonconversion_table)", charts.build_nonconversion_table, df, iterations=20)
    
    # 3. Benchmark other primary tabs for comparison
    tab1_res = run_benchmark("Tab 1: Executive Summary layout", charts.tab1, df, iterations=20)
    tab3b_res = run_benchmark("Tab 3b: Claims Breakdown layout", charts.tab3b, df, iterations=20)
    tab8_res = run_benchmark("Tab 8: Margin Analysis layout", charts.tab8, df, iterations=20)
    tab11_res = run_benchmark("Tab 11: Regional Analytics layout", charts.tab11, df, iterations=20)
    
    print_section("Benchmark Results Summary")
    results = [
        db_results,
        leads_kpi,
        leads_pivot,
        leads_pivot_detail,
        leads_nonconv,
        tab1_res,
        tab3b_res,
        tab8_res,
        tab11_res
    ]
    
    print(f"{'Module / Operation':<45} | {'Avg (ms)':<10} | {'Range (ms)':<12}")
    print("-" * 75)
    for r in results:
        if r:
            range_str = f"{r['min']:.1f}-{r['max']:.1f}"
            print(f"{r['label']:<45} | {r['mean']:<10.2f} | {range_str:<12}")
            
    print("\nVisual Comparison (Normalized Average Response Time):")
    all_means = [r['mean'] for r in results if r]
    max_mean = max(all_means) if all_means else 1
    
    for r in results:
        if r:
            bar_len = int((r['mean'] / max_mean) * 20)
            bar = "#" * bar_len + "-" * (20 - bar_len)
            print(f"  {r['label']:<40} [{bar}] {r['mean']:.2f} ms")
            
    print("\n[Recommendation] Live deployment targets:")
    print(" - UI rendering layouts should remain under 100ms for sub-second page transitions.")
    print(" - Database query time should stay below 500ms (or leverage caching) for smooth data refreshing.")
    print("=" * 65)

if __name__ == "__main__":
    main()
