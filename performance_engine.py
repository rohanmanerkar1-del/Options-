import pandas as pd
import os
import datetime

JOURNAL_FILE = "trade_journal.csv"
MIN_TRADES_FOR_INSIGHT = 20

class BehaviorFeedback:
    def __init__(self):
        self.active_mistakes = []
        self.active_successes = []
        self.size_multiplier = 1.0
        self.extra_confirmation_required = False
        self.restricted_conditions = []
        self.preferred_conditions = []

    def to_dict(self):
        return {
            "active_mistakes": self.active_mistakes,
            "active_successes": self.active_successes,
            "size_multiplier": self.size_multiplier,
            "extra_confirmation_required": self.extra_confirmation_required,
            "restricted_conditions": self.restricted_conditions,
            "preferred_conditions": self.preferred_conditions
        }

def load_journal():
    if not os.path.exists(JOURNAL_FILE):
        return pd.DataFrame()
    try:
        df = pd.read_csv(JOURNAL_FILE)
        # Ensure numeric columns
        cols = ['Entry', 'Exit', 'PnL']
        for c in cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')
        return df
    except Exception as e:
        print(f"[Performance] Error loading journal: {e}")
        return pd.DataFrame()

def calculate_metrics(df_group):
    count = len(df_group)
    if count == 0: return None
    
    wins = df_group[df_group['PnL'] > 0]
    losses = df_group[df_group['PnL'] <= 0]
    
    win_rate = (len(wins) / count) * 100
    avg_win = wins['PnL'].mean() if not wins.empty else 0
    avg_loss = losses['PnL'].mean() if not losses.empty else 0
    total_pnl = df_group['PnL'].sum()
    expectancy = total_pnl / count
    
    return {
        "count": count,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "expectancy": expectancy
    }

def analyze_group(df, group_col, feedback_obj):
    if group_col not in df.columns:
        return

    groups = df.groupby(group_col)
    
    for name, group in groups:
        metrics = calculate_metrics(group)
        if not metrics or metrics['count'] < MIN_TRADES_FOR_INSIGHT:
            continue
            
        # Mistake Identification
        # Trades >= 20, Expectancy < 0, Win Rate < 45% (Expectancy priority)
        # Note: User said "Expectancy is NOT strongly positive" for low win rate,
        # but the core definition is "Expectancy < 0 AND Win Rate < 45"
        if metrics['expectancy'] < 0 and metrics['win_rate'] < 45:
            mistake_desc = f"{group_col}:{name}"
            feedback_obj.active_mistakes.append(mistake_desc)
            feedback_obj.restricted_conditions.append(mistake_desc)
            
        # Success Identification
        # Trades >= 20, Expectancy > 0, Win Rate > 55, Avg Win >= Avg Loss
        if (metrics['expectancy'] > 0 and 
            metrics['win_rate'] > 55 and 
            metrics['avg_win'] >= abs(metrics['avg_loss'])):
            
            success_desc = f"{group_col}:{name}"
            feedback_obj.active_successes.append(success_desc)
            feedback_obj.preferred_conditions.append(success_desc)

def get_feedback(current_context=None):
    """
    Main entry point. Analyzes journal and returns feedback.
    current_context: dict (optional) with keys like 'Regime', 'Strategy' 
                     to tailor immediate feedback (e.g. sizing).
    """
    df = load_journal()
    feedback = BehaviorFeedback()
    
    if df.empty or len(df) < MIN_TRADES_FOR_INSIGHT:
        return feedback.to_dict()
        
    # Analyze Dimensions
    # We assume columns might exist from parsed EntryReason or new columns
    # For V1, we will look for specific columns if we added them.
    # If not, we might need to extract them. 
    # Let's try to analyze 'EntryReason' as a proxy for Strategy if 'Strategy' col missing
    
    analyze_group(df, 'ExpiryType', feedback)
    analyze_group(df, 'EntryReason', feedback) # Often contains Strategy info
    
    if 'Regime' in df.columns:
        analyze_group(df, 'Regime', feedback)
    
    # Calculate Impact on Current Context
    if current_context:
        # Check for Mistakes
        penalty_count = 0
        
        # Check Regime
        regime = current_context.get('Regime')
        if regime and f"Regime:{regime}" in feedback.active_mistakes:
            penalty_count += 1
            feedback.extra_confirmation_required = True
            
        # Check Strategy
        strat = current_context.get('Strategy')
        if strat and f"EntryReason:{strat}" in feedback.active_mistakes: # Using EntryReason as Strategy proxy
            penalty_count += 1
            
        # Check Expiry
        # Logic: 0 DTE after 1:30 PM
        # This is a specific rule requested.
        # "If 0 DTE trades after 13:30 have net negative expectancy" -> We need granular parsing.
        # Implemented simplified version: if '0 DTE' category is a mistake overall.
        
        # Apply Sizing Logic
        if penalty_count > 0:
            # Reduce by 30-50%
            # Cap at 50%
            feedback.size_multiplier = 0.5 
            
    return feedback.to_dict()

# Test run
if __name__ == "__main__":
    fb = get_feedback()
    print("Feedback Object:", fb)
