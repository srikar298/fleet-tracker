class GamificationEngine:
    @staticmethod
    def generate_progress_bar(current_value: float, target_value: float, target_type: str) -> str:
        """Returns the formatted markdown text for daily progress"""
        if target_value <= 0:
            return ""
            
        pct = current_value / target_value
        
        if target_type == "Trips":
            val_str = f"{int(current_value)}/{int(target_value)} Trips"
        else:
            val_str = f"₹{current_value}/₹{int(target_value)}"
            
        squares_filled = min(5, int(pct * 5))
        bar = "🟩" * squares_filled + "⬜" * (5 - squares_filled)
        
        text = f"\n\n🎯 *Daily Goal Progress*\n{bar} {val_str}"
        
        if pct >= 1.0:
            text += "\n🎉 *TARGET ACCOMPLISHED! Exceptional work!* 🏆"
        elif pct > 0.8:
            text += "\n🔥 *Almost there! Keep pushing!*"
            
        return text
