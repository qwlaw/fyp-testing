import speech_recognition as sr
import preprocess as pp
import streamlit as st
import model as md
import shelve
import time
import ner

USER_AVATAR = "👤"
BOT_AVATAR = "🤖"

# Load chat history from shelve file
def load_history(name="chat_history"):
    with shelve.open(name) as db:
        return db.get("messages", [])

# Save chat history to shelve file
def save_history(messages, name="chat_history"):
    with shelve.open(name) as db:
        db["messages"] = messages

def handle_sidebar():
    docs_collection = st.file_uploader("Upload your documents here", accept_multiple_files=True, type=["pdf", "docx", "txt", "md", "jpeg", "jpg", "png"])

    # Validate uploaded files
    valid_docs = []
    invalid_docs = []
    for file in docs_collection:
        if pp.validate_file_type(file):
            valid_docs.append(file)
        else:
            invalid_docs.append(file.name)

    if invalid_docs:
        st.error(f"The following files are invalid: {', '.join([file for file in invalid_docs])}")
        st.stop()  # Stop execution here if there are invalid files

    return docs_collection, valid_docs

def start_new_chat():
    # Save current chat history
    save_history(st.session_state.messages, name="old_chat_history")
    # Clear current chat history
    st.session_state.messages = []
    st.session_state.rawtext = []

def show_notification(message, type='info'):
    notification_placeholder = st.empty()
    notification_placeholder.markdown(f'<div style="position: fixed; top: 30px; right: 30px; padding: 0.5rem 1rem; margin: 20; background-color: {"#f63366" if type == "error" else "#00A36C"}; color: white; font-weight: bold; border-radius: 5px; box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1); z-index: 999;">{message}</div>', unsafe_allow_html=True)
    time.sleep(0.5)
    notification_placeholder.empty()

def main():
    st.set_page_config(page_title="Chat with multiple PDFs", page_icon=":books:")
    st.title("PDFs Chatbot Interface :books:")
    st.markdown("This is a chatbot interface that allows you to upload PDFs and ask questions about them.")
    
    # Initialize or load chat history
    if "messages" not in st.session_state:
        st.session_state.messages = load_history()

    # Initialize or load chat history
    if "rawtext" not in st.session_state:
        st.session_state.rawtext = []
        
    # Initialize recording state
    if "recording" not in st.session_state:
        st.session_state.recording = False

    # Sidebar
    with st.sidebar:
        st.subheader("Your documents")
        docs_collection, valid_docs = handle_sidebar()
    
        # Display uploaded files' button
        if valid_docs:
            if st.button("Process", use_container_width=True):
                with st.spinner("Processing..."):
                    st.session_state.rawtext = pp.preprocess_document(docs_collection)                    
                show_notification("Documents processed successfully!")
                ner.ner_main(st.session_state.rawtext)
    
        if st.button("Delete Chat History", use_container_width=True):
            st.session_state.messages = []
            save_history([])
            show_notification("Chat history has been deleted.")
            
        if st.button("Start New Chat", use_container_width=True):
            start_new_chat()
            show_notification("New chat started. Old chat history stored!", type='success')
        
        if st.button("Show Old Chat History", use_container_width=True):
            show_notification("Old chat history restored!", type='success')
            st.session_state.messages = load_history(name="old_chat_history")
    

    # Display chat messages
    for message in st.session_state.messages:
        avatar = USER_AVATAR if message["role"] == "user" else BOT_AVATAR
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])
            
    # Main chat interface
    if prompt := st.chat_input("How can I help?"):
        st.session_state.messages.append({"role": "user", "content": prompt})  
        with st.chat_message("user", avatar=USER_AVATAR):
            st.markdown(prompt)
        
    response = None

    # Process user input and display using the bot
    if prompt:
        with st.chat_message("assistant", avatar=BOT_AVATAR):
            with st.spinner("Thinking..."):
                if prompt and st.session_state.rawtext:  
                    # This is the part where the model is called
                    response, mode = md.model(prompt, st.session_state.rawtext)

                    if mode == 'summarizer':
                        response = [sentence['summary_text'] for sentence in response]
                        response = ' '.join(response)
                    else:
                        response = response['answer']
                    
                    response = pp.post_process(response)
                    st.markdown(response)
                elif prompt and not st.session_state.rawtext:
                    response = "Please upload PDFs before asking questions!!"
                    st.markdown(response)
                    
    elif not st.session_state.messages:
         with st.chat_message("assistant", avatar=BOT_AVATAR):
            response = "Hello! I am here to help you with your questions."
            st.markdown(response)

    if response is not None:
        st.session_state.messages.append({"role": "assistant", "content": response})

    # Start Speech Recognition button
    if st.button("Start Speech Recognition"):
        st.session_state.recording = True
        recognizer = sr.Recognizer()
        mic = sr.Microphone()
        try:
            with mic as source:
                st.write("Say something...")
                audio = recognizer.listen(source)

            try:
                user_input = recognizer.recognize_google(audio)
                st.session_state.messages.append({"role": "user", "content": user_input})
                with st.chat_message("user", avatar=USER_AVATAR):
                    st.markdown(user_input)

                response = None

                # Process user input and display using the bot
                with st.chat_message("assistant", avatar=BOT_AVATAR):
                    with st.spinner("Thinking..."):
                        if user_input and st.session_state.rawtext:  # Check if context is not empty
                            response, mode = md.model(user_input, st.session_state.rawtext)
                            if mode == 'summarizer':
                                response = [sentence['summary_text'] for sentence in response]
                                response = ' '.join(response)
                            else:
                                response = response['answer']
                            st.markdown(response)
                        elif not st.session_state.rawtext:
                            show_notification("Please upload PDFs before asking questions!", type='error')

                st.session_state.messages.append({"role": "assistant", "content": response if response else ""})

                # Save chat history after each interaction
                save_history(st.session_state.messages)

            except sr.UnknownValueError:
                st.error("Sorry, could not understand audio.")
            except sr.RequestError as e:
                st.error(f"Could not request results; {e}")
        except Exception as e:
            st.error(f"An error occurred: {e}")
        finally:
            if mic.stream is not None:
                mic.stream.close()  # Explicitly close the microphone stream
            st.session_state.recording = False

    # Stop speech recognition
    if st.session_state.recording:
        if st.button("Stop Speech Recognition"):
            st.session_state.recording = False



    # Save chat history after each interaction
    save_history(st.session_state.messages)

if __name__ == '__main__':
    main()
