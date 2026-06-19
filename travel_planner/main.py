from .llm import extract_inputs, generate_confirmation, generate_response
from .models import TripContext
from .prompts import OPENING_MESSAGE


def run() -> None:
    trip_context = TripContext()
    conversation_history = []

    print(f"\nAssistant: {OPENING_MESSAGE}\n")

    while not trip_context.is_confirmed:
        user_message = input("> ").strip()
        if not user_message:
            continue

        conversation_history.append({"role": "user", "content": user_message})

        extracted = extract_inputs(user_message, trip_context)
        trip_context.update(extracted)

        if trip_context.is_complete() and not trip_context.is_confirmed:
            confirmation = generate_confirmation(trip_context)
            print(f"\nAssistant: {confirmation}\n")
            conversation_history.append({"role": "assistant", "content": confirmation})

            answer = input("> ").strip().lower()
            conversation_history.append({"role": "user", "content": answer})

            if answer in ("yes", "y", "looks good", "correct", "that's right", "yep", "yeah"):
                trip_context.is_confirmed = True
                if trip_context.destination:
                    print("\n[PLANNING phase]\n")
                else:
                    print("\n[SUGGESTION phase]\n")
            else:
                # User wants to change something — let the response loop handle it
                response = generate_response(trip_context, answer, conversation_history[:-1])
                print(f"\nAssistant: {response}\n")
                conversation_history.append({"role": "assistant", "content": response})
        else:
            response = generate_response(trip_context, user_message, conversation_history[:-1])
            print(f"\nAssistant: {response}\n")
            conversation_history.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    run()
