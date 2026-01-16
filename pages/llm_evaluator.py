import streamlit as st
import pandas as pd
import autogen
from openai import OpenAI
import time
import re
import io

st.set_page_config(layout="wide", page_title="LLM-based Evaluation", page_icon="🤖")

st.title("LLM-based Evaluation")

# Initialize session state for storing results and tasks
if "evaluation_results" not in st.session_state:
    st.session_state.evaluation_results = []
    
if "tasks" not in st.session_state:
    st.session_state.tasks = []

# Initialize the task input handling
if "new_task" not in st.session_state:
    st.session_state.new_task = ""

def add_task():
    if st.session_state.new_task and st.session_state.new_task not in st.session_state.tasks:
        st.session_state.tasks.append(st.session_state.new_task)
        st.session_state.new_task = ""

st.markdown("""
### 📜 How It Works
This is an LLM-based evaluation system that compares a multi-agent system (Dragonshield) against a single-agent system (JSA Advisor) for Job Safety Analysis (JSA) of construction tasks. 
The system will:

1. Use Dragonshield (multi-agent system) to conduct a comprehensive JSA
2. Use JSA Advisor (single-agent system) to conduct a JSA
3. Compare and evaluate both approaches
4. Generate an impartial judgment on which system performed better

### ⚙️ Setup
Please provide your OpenAI API key to use this tool. Your API key is required to run the LLM agents.
""")

# API Key Input
api_key = st.text_input("Enter your OpenAI API key", type="password")

# Task management
st.subheader("Enter Construction Tasks for JSA Analysis")

# Task input and add button
col1, col2 = st.columns([3, 1])
with col1:
    task_input = st.text_area("Enter a construction task:", placeholder="Example: Portable Air Compressor Usage", key="new_task")
with col2:
    st.button("Add Task", key="add_task", on_click=add_task)

# Display tasks
if st.session_state.tasks:
    st.subheader("Tasks for Evaluation")
    for i, task in enumerate(st.session_state.tasks):
        col1, col2 = st.columns([5, 1])
        with col1:
            st.text(f"{i+1}. {task}")
        with col2:
            if st.button("Remove", key=f"remove_{i}"):
                st.session_state.tasks.pop(i)
                st.experimental_rerun()

# Function to check for markers in judge's response
def check_markers_in_content(response_text):
    """Check if response contains markers [[A]] or [[B]]"""
    a_exists = bool(re.search(r'\[\[A\]\]', response_text))
    b_exists = bool(re.search(r'\[\[B\]\]', response_text))
    return a_exists, b_exists

# Function to generate Excel file for download
def generate_excel():
    if not st.session_state.evaluation_results:
        return None
    
    df = pd.DataFrame(st.session_state.evaluation_results)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='JSA Evaluations', index=False)
        # Auto-adjust columns' width
        worksheet = writer.sheets['JSA Evaluations']
        for i, col in enumerate(df.columns):
            # Find the maximum length of the column
            column_len = max(df[col].astype(str).map(len).max(), len(col))
            worksheet.set_column(i, i, column_len + 2)  # Add a little extra space
    
    buffer.seek(0)
    return buffer

# Function to run JSA evaluation for a single task
def run_jsa_evaluation(task, api_key, status):
    try:
        # Initialize client
        client = OpenAI(api_key=api_key)
        
        status.update(label=f"Setting up Dragonshield multi-agent system for task: {task[:30]}...")
        
        # Common LLM configuration
        model_config = {"config_list": [{"model": "gpt-4-1106-preview", "temperature": 0.1, "api_key": api_key}]}
        
        # Initialize agents with the exact prompts provided
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

        status.update(label=f"Setting up group chat for task: {task[:30]}...")
        
        # Setup group chat
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

        status.update(label=f"Running Dragonshield multi-agent JSA analysis for task: {task[:30]}...")
        
        # Start the conversation
        start_time = time.time()
        
        # Run the conversation for multi-agent (Dragonshield)
        response = user_proxy.initiate_chat(
            manager,
            message=task,
        )
        
        multi_agent_time = time.time() - start_time
        
        status.update(label=f"Multi-agent analysis completed in {multi_agent_time:.2f} seconds! Generating single-agent response...")
        
        # Generate JSA Advisor (single-agent) response
        status.update(label=f"Generating JSA Advisor (single-agent) response for task: {task[:30]}...")
        
        single_agent_start_time = time.time()
        
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
                {"role": "user", "content": task}
            ]
        )
        
        single_agent_time = time.time() - single_agent_start_time
        
        # Get the JSA Advisor response
        jsa_advisor_response = jsa_advisor.choices[0].message.content
        
        status.update(label=f"Comparing responses (First run) for task: {task[:30]}...")
        
        judge_start_time = time.time()
        
        # Extract Dragonshield (multi-agent) response
        dragonshield_response = ""
        for message in response.chat_history:
            if message.get('name') == 'ReporterAgent':
                dragonshield_response = message.get('content')
                break
        
        # First comparison: JSA Advisor (single-agent) vs Dragonshield (multi-agent)
        judge_prompt = """Please act as an impartial judge and evaluate the quality of the responses provided by two AI assistants regarding a job safety analysis (JSA) in construction. The task involves breaking down the scope of a job into its component steps, identifying hazards associated with each step, evaluating the hazards in terms of likelihood and impact, determining preventive measures for high and moderate-risk hazards, and providing a report of these findings. Your evaluation should consider correctness, completeness, and helpfulness.
        
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

        Compare the two JSA responses marked as [[A]] and [[B]] at the end of your evaluation, explicitly state which response you think is better and why in a detailed explanation. You must clearly indicate which response is better by saying "[[A]]" or "[[B]]" is better. If you think they're equally good, state "Both responses are equally good".

        For each JSA report, consider:
        1. Clarity and structure of the job breakdown
        2. Comprehensiveness of hazard identification
        3. Accuracy of risk assessments (likelihood and impact)
        4. Practicality and comprehensiveness of preventive measures
        5. Overall quality and usefulness for ensuring safety
        """
        
        jsa_judge = client.chat.completions.create(
            model="gpt-4-1106-preview",
            messages=[
                {"role": "system", "content": judge_prompt},
                {"role": "user", "content": f"The task was: {task}\n\nResponse A:\n{jsa_advisor_response}\n\nResponse B:\n{dragonshield_response}"}
            ]
        )
        
        judge_response = jsa_judge.choices[0].message.content
        
        # For fair comparison, let's also run with swapped positions
        status.update(label=f"Comparing responses (Second run) for task: {task[:30]}...")
        
        jsa_judge_swapped = client.chat.completions.create(
            model="gpt-4-1106-preview",
            messages=[
                {"role": "system", "content": judge_prompt},
                {"role": "user", "content": f"The task was: {task}\n\nResponse A:\n{dragonshield_response}\n\nResponse B:\n{jsa_advisor_response}"}
            ]
        )
        
        judge_response_swapped = jsa_judge_swapped.choices[0].message.content
        
        # Check which system was preferred in each comparison
        a_exists, b_exists = check_markers_in_content(judge_response)
        a_exists_swapped, b_exists_swapped = check_markers_in_content(judge_response_swapped)
        
        # Determine the final winner
        if (a_exists and not b_exists) and (b_exists_swapped and not a_exists_swapped):
            # JSA Advisor won both comparisons
            winner = "JSA Advisor (Single-agent)"
        elif (b_exists and not a_exists) and (a_exists_swapped and not b_exists_swapped):
            # Dragonshield won both comparisons
            winner = "Dragonshield (Multi-agent)"
        else:
            # Mixed results or ties
            winner = "Tie or inconclusive"
        
        judge_time = time.time() - judge_start_time
        total_time = time.time() - start_time
        
        status.update(label=f"Finalizing results for task: {task[:30]}...", state="complete")
        
        # Prepare results
        results = {
            "Task": task,
            "Dragonshield Response": dragonshield_response,
            "JSA Advisor Response": jsa_advisor_response, 
            "Judge Response 1": judge_response,
            "Judge Response 2": judge_response_swapped,
            "Winner": winner,
            "Dragonshield Time": f"{multi_agent_time:.2f}s",
            "JSA Advisor Time": f"{single_agent_time:.2f}s",
            "Judge Time": f"{judge_time:.2f}s",
            "Total Time": f"{total_time:.2f}s"
        }
        
        # Add to session state
        st.session_state.evaluation_results.append(results)
        
        return results
        
    except Exception as e:
        status.error(f"An error occurred: {str(e)}")
        return None

# Run Evaluation button
if api_key and st.session_state.tasks:
    if st.button("Run Evaluation"):
        with st.status("Running evaluations...", expanded=True) as status:
            # Run evaluations for each task
            for i, task in enumerate(st.session_state.tasks):
                status.update(label=f"Processing task {i+1}/{len(st.session_state.tasks)}: {task[:30]}...")
                run_jsa_evaluation(task, api_key, status)
            
            status.update(label="All evaluations completed!", state="complete")

# Display evaluation results if available
if st.session_state.evaluation_results:
    st.header("Evaluation Results")
    
    # Add download button for Excel
    excel_data = generate_excel()
    if excel_data:
        st.download_button(
            label="Download Results as Excel",
            data=excel_data,
            file_name="jsa_evaluation_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    # Create and display summary table
    st.subheader("Summary of Evaluations")
    summary_data = []
    for i, result in enumerate(st.session_state.evaluation_results):
        # Determine winner of first run (JSA Advisor vs Dragonshield)
        first_run_winner = "JSA Advisor" if "[[A]]" in result["Judge Response 1"] else "Dragonshield" if "[[B]]" in result["Judge Response 1"] else "Tie"
        
        # Determine winner of second run (Dragonshield vs JSA Advisor)
        second_run_winner = "Dragonshield" if "[[A]]" in result["Judge Response 2"] else "JSA Advisor" if "[[B]]" in result["Judge Response 2"] else "Tie"
        
        # Final winner is already calculated in the result
        winner_text = result["Winner"]
        
        summary_data.append({
            "Task Description": result["Task"][:80] + "..." if len(result["Task"]) > 80 else result["Task"],
            "Run 1 Winner": first_run_winner,
            "Run 2 Winner": second_run_winner,
            "Final Winner": winner_text,
            "Dragonshield": result.get("Dragonshield Time", "N/A"),
            "JSA Advisor": result.get("JSA Advisor Time", "N/A"),
            "Total Time": result.get("Total Time", "N/A")
        })
    
    summary_df = pd.DataFrame(summary_data)
    
    # Apply styling to the dataframe
    def highlight_winner(val):
        if 'Dragonshield' in val:
            return 'background-color: #d4f1f9; font-weight: bold'
        elif 'JSA Advisor' in val:
            return 'background-color: #ffe6e6; font-weight: bold'
        elif 'Tie' in val:
            return 'background-color: #f0f0f0; font-style: italic'
        return ''
    
    styled_df = summary_df.style.applymap(highlight_winner, subset=['Run 1 Winner', 'Run 2 Winner', 'Final Winner'])
    st.dataframe(styled_df, use_container_width=True, height=min(350, len(summary_data)*60 + 40))
    
    # Calculate statistics
    if len(summary_data) > 0:
        dragonshield_wins = sum(1 for r in st.session_state.evaluation_results if "Dragonshield" in r["Winner"])
        jsa_advisor_wins = sum(1 for r in st.session_state.evaluation_results if "JSA Advisor" in r["Winner"])
        ties = sum(1 for r in st.session_state.evaluation_results if "Tie" in r["Winner"])
        
        st.subheader("Overall Results")
        col1, col2, col3 = st.columns(3)
        col1.metric("Dragonshield Wins", dragonshield_wins)
        col2.metric("JSA Advisor Wins", jsa_advisor_wins)
        col3.metric("Ties/Inconclusive", ties)
    
    # Display each evaluation
    st.subheader("Detailed Results")
    for i, result in enumerate(st.session_state.evaluation_results):
        with st.expander(f"Task {i+1}: {result['Task'][:50]}...", expanded=i==len(st.session_state.evaluation_results)-1):
            st.subheader("Task")
            st.write(result['Task'])
            
            st.subheader("Dragonshield (Multi-agent) Response")
            st.markdown(result['Dragonshield Response'])
            
            st.subheader("JSA Advisor (Single-agent) Response")
            st.markdown(result['JSA Advisor Response'])
            
            st.subheader("Judge Analysis (First Comparison)")
            st.markdown(result['Judge Response 1'])
            
            st.subheader("Judge Analysis (Second Comparison - Positions Swapped)")
            st.markdown(result['Judge Response 2'])
            
            st.subheader("Final Result")
            st.info(f"**Winner:** {result['Winner']}")
            
            # Display time breakdown
            st.subheader("Execution Times")
            time_col1, time_col2, time_col3, time_col4 = st.columns(4)
            time_col1.metric("Dragonshield", result.get("Dragonshield Time", "N/A"))
            time_col2.metric("JSA Advisor", result.get("JSA Advisor Time", "N/A"))  
            time_col3.metric("Judge", result.get("Judge Time", "N/A"))
            time_col4.metric("Total", result.get("Total Time", "N/A"))
            
            # Add a separator between results
            if i < len(st.session_state.evaluation_results) - 1:
                st.markdown("---")

# Clear Results button 
if st.session_state.evaluation_results:
    if st.button("Clear All Results"):
        st.session_state.evaluation_results = []
        st.experimental_rerun() 