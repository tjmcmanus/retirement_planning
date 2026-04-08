#!/usr/bin/env python3
"""
Test chart generation directly to diagnose the issue.
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

def test_chart_generation():
    """Test chart generation with sample data."""
    print("Testing Chart Generation")
    print("=" * 60)
    
    # Create sample performance data
    sample_data = pd.DataFrame([
        {'Period': '3M', 'Return': -1.56, 'Benchmark': 1.75, 'Alpha': -3.31, 
         'Benchmark Name': 'S&P 500', 'Volatility': 15.2, 'Sharpe': 0.45, 'Max Drawdown': -5.2},
        {'Period': '6M', 'Return': 403.00, 'Benchmark': 3.44, 'Alpha': 399.56,
         'Benchmark Name': 'S&P 500', 'Volatility': 25.8, 'Sharpe': 1.85, 'Max Drawdown': -5.2},
        {'Period': '1Y', 'Return': 403.00, 'Benchmark': 7.00, 'Alpha': 396.00,
         'Benchmark Name': 'S&P 500', 'Volatility': 22.1, 'Sharpe': 1.92, 'Max Drawdown': -5.2}
    ])
    
    print("\nSample Data:")
    print(sample_data)
    print()
    
    # Test chart generation
    try:
        from components.reporting.report_builder import ReportBuilder
        
        # Create a dummy template
        class DummyTemplate:
            name = "Test"
            sections = []
            default_config = {}
        
        # We can't instantiate ReportBuilder directly, so let's test the chart method
        import plotly.graph_objects as go
        
        print("Generating chart...")
        
        # Prepare data
        periods = sample_data['Period'].tolist()
        returns = sample_data['Return'].tolist()
        benchmarks = sample_data['Benchmark'].tolist()
        benchmark_name = sample_data['Benchmark Name'].iloc[0]
        
        # Create figure
        fig = go.Figure()
        
        # Add portfolio returns bar
        fig.add_trace(go.Bar(
            name='Portfolio Return',
            x=periods,
            y=returns,
            marker_color='#2E86AB',
            text=[f'{r:+.1f}%' for r in returns],
            textposition='outside',
            textfont=dict(size=10, color='#2E86AB'),
            hovertemplate='<b>%{x}</b><br>Portfolio: %{y:.2f}%<extra></extra>'
        ))
        
        # Add benchmark bar
        fig.add_trace(go.Bar(
            name=f'Benchmark ({benchmark_name})',
            x=periods,
            y=benchmarks,
            marker_color='#A23B72',
            text=[f'{b:+.1f}%' for b in benchmarks],
            textposition='outside',
            textfont=dict(size=10, color='#A23B72'),
            hovertemplate='<b>%{x}</b><br>Benchmark: %{y:.2f}%<extra></extra>'
        ))
        
        # Update layout
        fig.update_layout(
            title={
                'text': 'Portfolio Performance vs Benchmark',
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16, 'color': '#1f2937'}
            },
            xaxis_title='Period',
            yaxis_title='Return (%)',
            barmode='group',
            height=400,
            width=800
        )
        
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True, zeroline=True)
        
        print("✅ Chart generated successfully!")
        print(f"   Chart type: {type(fig)}")
        print(f"   Has write_image: {hasattr(fig, 'write_image')}")
        
        # Test export
        try:
            fig.write_image('test_chart_debug.png', width=800, height=400)
            print("✅ Chart export successful!")
        except Exception as e:
            print(f"⚠️  Chart export failed: {e}")
        
        return fig
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_performance_data():
    """Test getting performance data."""
    print("\nTesting Performance Data Generation")
    print("=" * 60)
    
    try:
        from components.performance_tracker import get_tracker
        
        tracker = get_tracker()
        print("✅ Performance tracker initialized")
        
        # Test getting period performance
        periods = ['3M', '6M', '1Y']
        for period in periods:
            metrics = tracker.get_period_performance(period)
            if metrics:
                print(f"✅ {period}: TWR = {metrics.twr*100:+.2f}%")
            else:
                print(f"⚠️  {period}: No data")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == '__main__':
    print("Chart Generation Diagnostic")
    print("=" * 60)
    
    # Test performance data
    perf_ok = test_performance_data()
    
    # Test chart generation
    chart = test_chart_generation()
    
    print("\n" + "=" * 60)
    print("Diagnostic Summary")
    print("=" * 60)
    
    if perf_ok and chart:
        print("✅ Both performance data and chart generation working")
        print("   The issue may be in the integration or data format")
    elif perf_ok:
        print("✅ Performance data OK")
        print("❌ Chart generation failed")
    elif chart:
        print("❌ Performance data failed")
        print("✅ Chart generation OK")
    else:
        print("❌ Both performance data and chart generation failed")
    
    print("\nNext steps:")
    print("1. Check logs when generating report")
    print("2. Verify performance data format")
    print("3. Check if chart method is being called")

# Made with Bob
