import pdb
import numpy as np
import pandas as pd
pd.options.display.max_columns = 50
pd.options.display.max_colwidth = 80
from datetime import datetime
from datetime import timedelta
import scipy.stats as scs
import matplotlib.pyplot as plt


def update_column_names(df):
    #remove spaces from column names
    df.columns = df.columns.str.replace(' ', '_')
    return df


def convert_timedate(exam_df, course_df):
    #convert date/time columns from strings to date/time objects
    course_df['Elapsed_Time'].replace(to_replace='0000:00:00.00', value='00:00:00', inplace=True)
    exam_df['Exam_Date'] =  pd.to_datetime(exam_df['Exam_Date'], format='%Y-%m-%d')
    exam_df['Date_Recorded'] =  pd.to_datetime(exam_df['Date_Recorded'], format='%Y-%m-%d %H:%M:%S')
    exam_df['Certificate_Expiration_Date'] =  pd.to_datetime(exam_df['Certificate_Expiration_Date'], format='%Y-%m-%d')
    exam_df['Certifcate_Sent'] =  pd.to_datetime(exam_df['Certifcate_Sent'], format='%Y-%m-%d')
    course_df['Date_Ordered'] =  pd.to_datetime(course_df['Date_Ordered'], format='%Y-%m-%d')
    course_df['Date_Registered'] =  pd.to_datetime(course_df['Date_Registered'], format='%Y-%m-%d')
    course_df['Expiration_Date'] =  pd.to_datetime(course_df['Expiration_Date'], format='%Y-%m-%d')
    course_df['First_Login'] =  pd.to_datetime(course_df['First_Login'], format='%Y-%m-%d')
    course_df['Last_Login'] =  pd.to_datetime(course_df['Last_Login'], format='%Y-%m-%d')
    course_df['Date_Complete'] =  pd.to_datetime(course_df['Date_Complete'], format='%Y-%m-%d')
    course_df['Elapsed_Time'] =  pd.to_timedelta(course_df['Elapsed_Time'])

    return exam_df, course_df

def convert_pass_fail(exam_df):
    #convert Pass/Fail column to 1 = pass & 0 = fail
    exam_df['Exam_Status'] = exam_df['Exam_Status'].astype(str).str.strip()
    exam_df['Exam_Status'].replace(to_replace=('Passed', 'Failed'), value=(1,0), inplace=True)

    return exam_df


def filter_data(exam_df, course_df):

    #filter out paper exam records
    exam2 = exam_df[exam_df['Delivery_Type'] == 'Web']
    #filter out NULL EEID's
    exam3 = exam2[pd.notna(exam2['EmployeeID'])]
    #sort by Exam Date
    exam4 = exam3.sort_values(by = 'Exam_Date')
    #group exams by EEID and select the earliest/first attempt
    exam5 = exam4.loc[exam4.groupby('EmployeeID').Exam_Date.idxmin()]
    #filter out exams taken before 1/1/2017
    exam_df = exam5[exam5['Exam_Date'] >= '2017-01-01']
    #selecting courses with 10 or 11 sections complete as "course taken"
    course_df = course_df[(course_df['Current_Section'] > 9.0) & (course_df['Current_Section'] < 12.0)]

    return exam_df, course_df


def limit_cols(exam_df, course_df):
    #selecting columns from exam that I want to include in combined df
    exam_col = ['NRA_Person_ID', 'Exam_Name', 'Exam_Form', 'Language', 'Exam_Date', 'Date_Recorded', 'Raw_Score',
                'Pct_Score', 'Exam_Status','EmployeeID']

    #selecting columns from course that I want to include in combined df
    course_col = ['NRA_Person_ID', 'Course_Name', 'Date_Registered', 'Expiration_Date', 'First_Login', 'Last_Login',
                  'Date_Complete', 'Current_Section', 'Course_Status', 'Elapsed_Time', 'Post_Test_Percent_Score',
                  'EmployeeID']

    #limiting df columnms on those selections
    exam_df = exam_df[exam_col]
    course_df = course_df[course_col]

    return exam_df, course_df


def merge_dfs(exam_df, course_df):
    #merge exam and course dfs, inner join to allows each insatnce of course attributed to EEID to be lined up
    #with one instance (first attempt) for each EEID
    exam_course_df = exam_df.merge(course_df, how = 'inner', on = 'EmployeeID')

    return exam_course_df

def create_time_delta(exam_course_df):
    #create a time_delta column indicating the number of days bewteen course instance and exam instance
    exam_course_df['time_delta'] = exam_course_df['Exam_Date'] - exam_course_df['Last_Login']

    return exam_course_df

def return_first_attempts(exam_course_df):
    #remove records with time_delta less than 0 (this indicates that the course was taken after the first exam attempt)
    exam_course_df = exam_course_df[exam_course_df['time_delta'] >= pd.Timedelta(0, unit='d')]
    #sort values by time delta and reset index to allow us to select the course taken in closest proximity to the first exam
    #attempt
    exam_course_df = exam_course_df.sort_values('time_delta')
    exam_course_df.reset_index(drop=True)
    #select the course taken in closest proximity to the first exam attempt
    exam_course_df = exam_course_df.loc[exam_course_df.groupby('EmployeeID').time_delta.idxmin()]

    return exam_course_df

def create_comp_dfs(exam_course_df, time_delta):
    #select records only for employee who took the course less than week before the exam
    exam_course_df = exam_course_df[exam_course_df['time_delta'] <= time_delta]
    #create list of EEIDs to remove from larger set of exam records
    took_course_eeid = list(exam_course_df['EmployeeID'])
    #create df of exam records where course was not taken, or taken more than 7 days prior to exam
    exam_no_course_df = exam_hypoth_df[~exam_hypoth_df.EmployeeID.isin(took_course_eeid)]

    return exam_course_df, exam_no_course_df

def calulate_rates(exam_course_df, exam_no_course_df):
    #calculate total passes and attempts for each group to pass into a Beta distribution
    took_course_passes = np.sum(exam_course_df['Exam_Status'])
    took_course_attempts = exam_course_df.shape[0]
    no_course_passes = np.sum(exam_no_course_df['Exam_Status'])
    no_course_attempts = exam_no_course_df.shape[0]

    return took_course_passes, took_course_attempts, no_course_passes, no_course_attempts


def create_beta_dist(exam_course_df, exam_no_course_df):
    #create beta distributions
    took_course_passes, took_course_attempts, no_course_passes, no_course_attempts = calulate_rates(exam_course_df, exam_no_course_df)

    exam_course_dist = scs.beta(took_course_passes+1, took_course_attempts - took_course_passes +1)
    exam_no_course_dist = scs.beta(no_course_passes+1, no_course_attempts - no_course_passes +1)

    return exam_course_dist, exam_no_course_dist


def plot_dists(exam_course_dist, course_label, exam_no_course_dist, no_course_label, rv_samps = 10000):

    fig, ax = plt.subplots(figsize=(10, 6))
    bins = np.linspace(0.8, 1.0, 201)

    y_took_course = exam_course_dist.pdf(bins)
    y_no_course = exam_no_course_dist.pdf(bins)

    took_course_lines = ax.plot(bins, y_took_course, label = course_label, color = 'g')
    ax.fill_between(bins, y_took_course, alpha=0.2, color= 'g')

    no_course_lines = ax.plot(bins, y_no_course, label = no_course_label, color = 'r')
    ax.fill_between(bins, y_no_course, alpha=0.2, color= 'r')

    plt.legend(loc='upper right')
    plt.show()


def cred_int(dist, interval_size = .95):
    interval_size = 0.95
    tail_area = (1 - interval_size) / 2

    print("{0:0.1f}% credible interval for passing rate of employees who take the course within 7 days of taking the exam: {1:0.3f} (lower bound) - {2:0.3f} (upper bound)".format(
           interval_size *100,
           dist.ppf(tail_area),
           dist.ppf(1 - tail_area)))

def bar_plot(exam_course_df, exam_no_course_df, labels):
    #calculate total passes and attempts for each group to pass into a Beta distribution
    took_course_passes, took_course_attempts, no_course_passes, no_course_attempts = calulate_rates(exam_course_df, exam_no_course_df)


    passes = (took_course_passes, no_course_passes)
    fails = (took_course_attempts - took_course_passes, no_course_attempts - no_course_passes)
    course_pass_rate = took_course_passes / took_course_attempts
    no_course_pass_rate = no_course_passes / no_course_attempts

    N = 2
    ind = np.arange(N)
    width = 0.50

    p1 = plt.bar(ind, passes, width)
    p2 = plt.bar(ind, fails, width,
                 bottom=passes)

    plt.ylabel('Exams Taken')
    plt.title('Exam Results by Group')
    plt.xticks(ind, labels)
    plt.yticks(np.arange(0, no_course_attempts, 1000))
    plt.legend((p1[0], p2[0]), ('passes', 'fails'))

    plt.show()




if __name__ == '__main__':
    #read in text filed as pandas dataframes

    exam_df = pd.read_csv("/home/katie/01_galvanize_dsi/capstones/01capstone1/capstone1/data/ExamActivity_02062019_060002.txt", sep='|', parse_dates=True)
    course_df = pd.read_csv("/home/katie/01_galvanize_dsi/capstones/01capstone1/capstone1/data/CourseActivity_02062019_060007.txt", sep='|', parse_dates=True)

    exam_df = update_column_names(exam_df)
    course_df = update_column_names(course_df)
    exam_df, course_df = convert_timedate(exam_df, course_df)
    exam_df = convert_pass_fail(exam_df)
    exam_hypoth_df, course_hypoth_df = filter_data(exam_df, course_df)
    exam_hypoth_df, course_hypoth_df = limit_cols(exam_hypoth_df, course_hypoth_df)
    exam_course_df = merge_dfs(exam_hypoth_df, course_hypoth_df)
    exam_course_df = create_time_delta(exam_course_df)
    exam_course_df = return_first_attempts(exam_course_df)
    exam_course_7d_df, exam_no_course_7d_df = create_comp_dfs(exam_course_df, pd.Timedelta(7, unit='d'))
    exam_course_7d_dist, exam_no_course_7d_dist = create_beta_dist(exam_course_7d_df, exam_no_course_7d_df)
    plot_dists(exam_course_dist = exam_course_7d_dist, course_label = 'Took Course within 7 Days of Exam', exam_no_course_dist = exam_no_course_7d_dist, no_course_label = 'Course Not Taken or Taken More than 7 Days Prior', rv_samps = 10000)
    cred_int(exam_course_7d_dist, interval_size = .95)

    #create Bayesian Test for course taken any number of days prior to exam
    exam_course_df, no_course_ever_df = create_comp_dfs(exam_course_df, pd.Timedelta(2000, unit='d'))
    ever_took_course_dist, no_course_ever_dist =  create_beta_dist(exam_course_df, no_course_ever_df)
    plot_dists(exam_course_dist = ever_took_course_dist, course_label = 'Took Course at Some Point Prior to Exam', exam_no_course_dist = no_course_ever_dist, no_course_label = 'Course Not Taken Prior to Exam', rv_samps = 10000)

    #EDA Visualization
    bar_plot(exam_course_7d_df, exam_no_course_7d_df, labels = ('Took Course within \n 7 Days of Exam', 'Course Not Taken or Taken \n More than 7 Days Prior'))
    bar_plot(exam_course_df, no_course_ever_df, labels = ('Took Course at Some \n Point Prior to Exam', 'Course Not Taken Prior to Exam'))
