import streamlit as st
import random
import re
import autogen
from openai import OpenAI
from utils import display_response

# Page configuration
st.set_page_config(layout="wide", page_title="Human LLM Response Evaluation", page_icon="👤")

st.title("Human LLM Response Evaluation")

st.markdown("""
### 📜 How It Works
- **Blind Test:** Below are the responses of two LLM systems. One is a multi-agent system (Dragonshield) and the other is a single-agent system (JSA Advisor).
- **Vote for the Best:** We ask you to vote on which model generates a better JSA (Job Safety Analysis) report. 
- **Play Fair:** For fairness, their places are shuffled randomly between Response A and Response B. You can select either of them, a tie, or indicate that both are bad.
""")

# Initialize session state variables
if "response_mapping" not in st.session_state:
    st.session_state.response_mapping = {"A": "", "B": ""}
if "current_question" not in st.session_state:
    st.session_state.current_question = None
if "user_prompt" not in st.session_state:
    st.session_state.user_prompt = ""
if "final_mapping" not in st.session_state:
    st.session_state.final_mapping = None
if "responses_shuffled" not in st.session_state:
    st.session_state.responses_shuffled = False
if "selection_made" not in st.session_state:
    st.session_state.selection_made = False
if "custom_task_responses" not in st.session_state:
    st.session_state.custom_task_responses = {"A": "", "B": ""}

st.header("Enter Your Own Task")

# API Key Input
api_key = st.text_input("Enter your OpenAI API key", type="password", 
                         help="Required to generate responses for your custom task")

# Task input
custom_task = st.text_area("Enter your construction task for JSA analysis:", 
                          placeholder="Example: Portable Air Compressor Usage")

# Generate button
if st.button("Generate Responses") and api_key and custom_task:
    with st.status("Generating JSA analyses...", expanded=True) as status:
        try:
            # Initialize OpenAI client
            client = OpenAI(api_key=api_key)
            
            # Setup multi-agent system (Dragonshield)
            status.update(label="Setting up Dragonshield multi-agent system...")
            
            # Common LLM configuration
            model_config = {"config_list": [{"model": "gpt-4-1106-preview", "temperature": 0.1, "api_key": api_key}]}
            
            # Initialize agents for Dragonshield multi-agent system
            user_proxy = autogen.UserProxyAgent(
                name="Admin",
                system_message="A human admin.",
                code_execution_config=False,
                human_input_mode="TERMINATE"
            )

            project_manager_agent = autogen.AssistantAgent(
                name="ProjectManagerAgent",
                llm_config=model_config,
                system_message="""You are a highly skilled construction project manager with expertise in breaking down complex construction tasks into detailed, manageable steps. You excel at understanding the scope of a project and identifying all necessary actions to complete the job efficiently and safely. Your responsibility is to receive the scope and job information from the userproxy, and then meticulously decompose the job into clear, concise steps focusing on the implementation phase (max 5 steps). You will then send these steps to the SafetyInspectorAgent for further analysis. You can only send job steps to SafetyInspectorAgent. Ensure each step is comprehensive and directly related to the job's implementation.""",
            )

            safety_inspector_agent = autogen.AssistantAgent(
                name="SafetyInspectorAgent",
                llm_config=model_config,
                system_message="""You are a highly experienced safety inspector with a keen eye for identifying potential hazards in construction job processes. Your expertise lies in analyzing detailed job steps and recognizing possible risks that could arise during the implementation phase. Your task is to receive the job steps from the ProjectManagerAgent, meticulously evaluate each step, and identify any potential hazards associated with them. You will then send these identified hazards to the RiskAssessmentAgent. You can only send hazards to the RiskAssessmentAgent. Ensure that all identified hazards are relevant and clearly articulated for effective risk management.""",
            )

            risk_assessment_agent = autogen.AssistantAgent(
                name="RiskAssessmentAgent",
                llm_config=model_config,
                system_message="""You are a risk assessment specialist with extensive experience in evaluating and quantifying risks in construction projects. Your expertise lies in assessing the likelihood and impact of potential hazards. Your task is to receive the identified hazards from the SafetyInspectorAgent and FeedbackerAgent, analyze each hazard, and provide an assessment of its likelihood and impact based on the below scales. You have to write based on which criteria you choose these scales for each hazard. You will then send these assessments to the FeedbackerAgent.  In case your analyze needs to be fixed, you will receive feedback from the FeedbackerAgent. You'll need to change your scale and rewrite your analysis based on that feedback. Maybe this process of rewriting analyze will happen a few times until the FeedbackerAgent can't provide any more feedback. Never say "TERMINATE".

            Likelihood:
            - **P6: Almost Certain (>75%)**: The event is expected to occur during the project phase/facility life and has occurred several times on similar projects/facilities.
            - **P5: Likely (50% to 75%)**: The event has occurred sometime on a similar project or facility.
            - **P4: Possible (25% to 50%)**: Plausible to occur during the project phase or facility life.
            - **P3: Unlikely (5% to 25%)**: The event may occur in certain circumstances during the project phase or facility life.
            - **P2: Rare (1% to 5%)**: The event may occur in exceptional circumstances during the project phase or facility life.
            - **P1: Unforeseen (<1%)**: The event is not foreseen to occur during the project phase or facility life.
            Impact:
            - **C1: Insignificant**: Near hit incident. Low health effects/Recovery within hours.
            - **C2: Minor**: Minor injury/Medical treatment/Restricted workday case. Medium health effects, recovery in less than 6 days.
            - **C3: Moderate**: Moderate injury/Limited Lost time/Lost workday Case. Reversible incapacity health effects (Long & short absentee greater than 6 days).
            - **C4: Significant**: Significant injury/Extended lost time/Hospitalization. Long-term health effects.
            - **C5: Major**: One fatality or permanent incapacity (Occupational disability).
            - **C6: Catastrophic**: More than one fatality.
            """,
            )

            feedbacker_agent = autogen.AssistantAgent(
                name="FeedbackerAgent",
                llm_config=model_config,
                system_message="""As an experienced construction risk analyst, your role involves overseeing and providing feedback on risk analysis assessments. The RiskAssessmentAgent delivers analyses on the likelihoods and impacts of identified hazards. Your primary responsibility is to ensure the quality and efficiency of these analyses. You are tasked with reviewing these assessments and generating feedback reports on required improvements, without rewriting the analyses yourself. You have to iterate this process with the RiskAssessmentAgent until the RiskAssessmentAgent assessments are completely satisfied. Then, you can forward the identified hazards along with their likelihood and impact assessments to the RiskManagementAgent for further action.""",
            )

            risk_management_agent = autogen.AssistantAgent(
                name="RiskManagementAgent",
                llm_config=model_config,
                system_message="""You are a highly skilled risk management specialist with extensive experience in developing effective mitigation strategies for construction-related hazards. With your expertise in risk management, analyze the hazards and their assessments provided by the FeedbackerAgent. Develop and document effective mitigation strategies for each significant risk, ensuring these strategies are practical and detailed before forwarding them to the ReporterAgent.""",
            )

            reporter_agent = autogen.AssistantAgent(
                name="ReporterAgent",
                llm_config=model_config,
                system_message="""You are an expert communicator and report writer with a strong background in construction safety and risk management. Your role is to compile and synthesize information to create comprehensive and clear final reports. Your task is to receive the job steps from the ProjectManagerAgent, the identified hazards and their risk assessments from the FeedbackerAgent, and the preventive measures for high and moderate-risk hazards from the RiskManagementAgent. You will organize this information into a structured table, ensuring that each job step, associated high and moderate-risk hazard, likelihood and impact assessment, and preventive measure is clearly presented. Once the table is complete, you will create a final report summarizing the findings and recommendations. When the JSA process is complete, you will announce 'TERMINATE'. Ensure that the final report is thorough, accurate, and easy to understand.""",
            )
            
            # Setup group chat for Dragonshield
            groupchat = autogen.GroupChat(
                agents=[user_proxy, project_manager_agent, safety_inspector_agent, risk_assessment_agent, 
                        feedbacker_agent, risk_management_agent, reporter_agent], 
                messages=[], 
                max_round=10
            )

            manager = autogen.GroupChatManager(
                groupchat=groupchat, 
                llm_config=model_config,
                system_message="""You are a highly efficient and organized project coordinator with extensive experience in managing collaborative tasks and workflows in the construction sector. Your role is to ensure smooth communication and adherence to risk management protocols among the various AI agents: ProjectManagerAgent, SafetyInspectorAgent, RiskAssessmentAgent, FeedbackerAgent, ProjectManagerAgent, and ReporterAgent. Your task is to oversee the workflow, ensure each agent completes their tasks accurately and on time, and address any issues that arise during the process. You will facilitate the seamless handover of information between agents and ensure that the final output meets the workshop's goals. you have to send assessments from RiskAssessmentAgent to RiskAssessmentFeedbackAgent.""",
            )
            
            # Run the Dragonshield multi-agent system
            status.update(label="Running Dragonshield multi-agent JSA analysis...")
            response = user_proxy.initiate_chat(
                manager,
                message=custom_task,
            )
            
            # Extract Dragonshield (multi-agent) response
            dragonshield_response = ""
            for message in response.chat_history:
                if message.get('name') == 'ReporterAgent':
                    dragonshield_response = message.get('content')
                    break
            
            # Generate JSA Advisor (single-agent) response
            status.update(label="Generating JSA Advisor (single-agent) response...")
            jsa_advisor_prompt = """You are tasked with conducting a complete Job Safety Analysis (JSA) from start to finish. Here is your workflow: Receive Project Scope: Begin by collecting the scope of the construction project and the specific job/task from the UserProxy. Break down the job/task into detailed implementation steps, focusing on each action needed to complete it efficiently and safely. For each job step, identify potential hazards that could arise during the implementation. Assess the likelihood and impact of each identified hazard using the below information:
            
            Likelihood:
            - **P6: Almost Certain (>75%)**: The event is expected to occur during the project phase/facility life and has occurred several times on similar projects/facilities.
            - **P5: Likely (50% to 75%)**: The event has occurred sometime on a similar project or facility.
            - **P4: Possible (25% to 50%)**: Plausible to occur during the project phase or facility life.
            - **P3: Unlikely (5% to 25%)**: The event may occur in certain circumstances during the project phase or facility life.
            - **P2: Rare (1% to 5%)**: The event may occur in exceptional circumstances during the project phase or facility life.
            - **P1: Unforeseen (<1%)**: The event is not foreseen to occur during the project phase or facility life.
            Impact:
            - **C1: Insignificant**: Near hit incident. Low health effects/Recovery within hours.
            - **C2: Minor**: Minor injury/Medical treatment/Restricted workday case. Medium health effects, recovery in less than 6 days.
            - **C3: Moderate**: Moderate injury/Limited Lost time/Lost workday Case. Reversible incapacity health effects (Long & short absentee greater than 6 days).
            - **C4: Significant**: Significant injury/Extended lost time/Hospitalization. Long-term health effects.
            - **C5: Major**: One fatality or permanent incapacity (Occupational disability).
            - **C6: Catastrophic**: More than one fatality.

            Determine preventive measures for high and moderate-risk hazards. Compile all data into a structured table listing job steps, associated hazards, their assessments, and preventive measures: Job Step, Hazard, Likelihood (P), Impact (C), and Preventive Measures. Create a final comprehensive report summarizing the findings and recommendations. Communication should be formal and technical, providing clear and precise information."""
            
            jsa_advisor = client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=[
                    {"role": "system", "content": jsa_advisor_prompt},
                    {"role": "user", "content": custom_task}
                ]
            )
            
            # Get the JSA Advisor response
            jsa_advisor_response = jsa_advisor.choices[0].message.content
            
            # Store responses in session state
            st.session_state.custom_task_responses = {
                "Dragonshield (Multi-agent)": dragonshield_response,
                "JSA Advisor (Single-agent)": jsa_advisor_response
            }
            
            # Set up for comparison
            original_mapping = {
                "Dragonshield (Multi-agent)": dragonshield_response,
                "JSA Advisor (Single-agent)": jsa_advisor_response
            }
            
            shuffled = list(original_mapping.items())
            random.shuffle(shuffled)
            
            st.session_state.response_mapping = {
                "A": {"response": shuffled[0][1], "model": shuffled[0][0]},
                "B": {"response": shuffled[1][1], "model": shuffled[1][0]}
            }
            
            st.session_state.final_mapping = st.session_state.response_mapping.copy()
            st.session_state.responses_shuffled = True
            st.session_state.current_question = None
            
            status.update(label="Responses generated successfully!", state="complete")
            
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

# Display responses if available
if st.session_state.responses_shuffled and st.session_state.final_mapping and st.session_state.final_mapping["A"] and st.session_state.final_mapping["B"]:
    st.subheader("Choose the Better LLM Response")
    with st.form("response_form"):
        col1, col2 = st.columns(2, gap="large")

        with col1:
            st.subheader("Response A")
            display_response(st.session_state.final_mapping["A"]["response"])

        with col2:
            st.subheader("Response B")
            display_response(st.session_state.final_mapping["B"]["response"])

        # User interaction buttons
        col_b1, col_b2, col_b3, col_b4 = st.columns(4)
        with col_b1:
            a_better = st.form_submit_button("👈 A is better")
        with col_b2:
            b_better = st.form_submit_button("👉 B is better")
        with col_b3:
            tie = st.form_submit_button("🤝 Tie")
        with col_b4:
            both_bad = st.form_submit_button("👎 Both are bad")

        # Display the user selection result and map back to the model
        if not st.session_state.selection_made:
            if a_better:
                st.session_state.selection_made = True
                st.success(f"You selected: A is better (Model: {st.session_state.final_mapping['A']['model']})")
            elif b_better:
                st.session_state.selection_made = True
                st.success(f"You selected: B is better (Model: {st.session_state.final_mapping['B']['model']})")
            elif tie:
                st.session_state.selection_made = True
                st.success("You selected: It's a tie")
            elif both_bad:
                st.session_state.selection_made = True
                st.success("You selected: Both are bad") 