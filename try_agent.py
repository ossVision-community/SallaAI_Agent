#!/usr/bin/env python3
import sys
import os
from dotenv import load_dotenv

# Load env vars before importing Core.config to avoid RuntimeError
load_dotenv()

# Check keys before import to give a better error message
if not os.getenv("OPENAI_API_KEY"):
    print("❌ Error: OPENAI_API_KEY is not set in environment or .env file.")
    print("Please create a .env file with OPENAI_API_KEY=sk-...")
    sys.exit(1)

try:
    from Agent import build_app, AgentState
except ImportError as e:
    # If run from a different directory, we might need to adjust path
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    try:
        from Agent import build_app, AgentState
    except ImportError:
        print(f"❌ Error importing Agent: {e}")
        print("Make sure you are running this script from the project root.")
        sys.exit(1)
except RuntimeError as e:
    print(f"❌ Configuration Error: {e}")
    sys.exit(1)

def main():
    print("\n🛒 SallaAI Shopping Agent CLI")
    print("============================")
    
    if not os.getenv("SEARCHAPI_KEY"):
        print("⚠️  Warning: SEARCHAPI_KEY is not set. Real search results will be limited/failed.")
    
    print("Type a product name to search (or 'q' to quit, 'reset' to start over)")
    
    # Store context for multi-turn conversation
    conversation_context = None
    
    while True:
        # Change prompt based on whether we're in a follow-up
        prompt = "\nAnswer > " if conversation_context else "\nSearch query > "
        
        try:
            user_input = input(prompt).strip()
        except KeyboardInterrupt:
            print("\nExiting...")
            break
            
        if user_input.lower() in ('q', 'quit', 'exit'):
            break
            
        if user_input.lower() == 'reset':
            conversation_context = None
            print("🔄 Context cleared. Ready for new search.")
            continue
            
        if not user_input:
            continue
            
        # If we have pending context (previous question), append the answer
        if conversation_context:
            full_query = f"{conversation_context} {user_input}"
            print(f"ℹ️  Refining search with: '{full_query}'")
        else:
            full_query = user_input
            print(f"\n🤖 Agent is working on: '{full_query}'...")
        
        app = build_app()
        
        init_state: AgentState = {
            "query": full_query,
            "offers": [],
            "missing": [],
            "tried_tools": [],
            "steps": 0,
            "done": False,
            "errors": [],
            "trusted_only": False, 
        }
        
        try:
            # Use invoke() to get the complete final state (not stream deltas)
            final_state = app.invoke(init_state)
            
            if final_state:
                # Update context based on result
                if final_state.get("needs_more_info"):
                    # Keep the current accumulated query as context for the next turn
                    conversation_context = full_query
                    
                    # Print the follow-up question
                    question = final_state.get("follow_up_question")
                    result = final_state.get("result", {})
                    notes = result.get("notes", "")
                    
                    msg = question or notes
                    if not msg:
                        # Fallback if both are empty but flag is True (should not happen often)
                        msg = "Could you provide more details about your request?"
                    
                    print(f"\n❓ Agent needs info: {msg}")
                    continue # Skip the rest and wait for user input
                else:
                    # Request satisfied, clear context
                    conversation_context = None
                
                result = final_state.get("result", {})
                items = result.get("items", [])
                notes = result.get("notes", "")
                
                if notes:
                    print(f"\n📝 Note: {notes}")
                
                if items:
                    item = items[0]  # THE best recommendation
                    name = item.get('name', 'Unknown')
                    price = item.get('price', 'N/A')
                    currency = item.get('currency', 'SAR')
                    retailer = item.get('retailer', 'Unknown')
                    link = item.get('link', '#')
                    condition = item.get('condition', 'New')
                    reason = item.get('reason', '')
                    
                    print(f"\n✅ My Recommendation:")
                    print(f"   📦 {name}")
                    print(f"   💰 {price} {currency} | 🏪 {retailer}")
                    if reason:
                        print(f"   💡 {reason}")
                    print(f"   🔗 {link}")
                else:
                    print("\n❌ No matching products found.")
                    if final_state.get("errors"):
                        print(f"Errors: {final_state['errors']}")
                        
            else:
                print("\n❌ Agent did not complete successfully.")
                
        except Exception as e:
            print(f"\n❌ Error during execution: {e}")
            # import traceback
            # traceback.print_exc()

if __name__ == "__main__":
    main()

