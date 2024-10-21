#!/bin/bash

# Get the directory of the script
script_dir="$(dirname "$(readlink -f "$0")")"

# Log file path
log_file="${script_dir}/cron_log.txt"

# List of folder paths
folders=(
    "./Work"
    "./FailedPatients"
    "./HL7gen"
    "./Import"
    "./SentHL7"
    "./UnsentHL7"
    "./UploadedPatients"
    "./output"
)

# Clear contents every week at midnight on Sunday (day 0)
cron_frequency="0 0 * * 0"

# Backup current crontab
crontab -l > current_cron_jobs

# Start logging
echo "---- Cron Setup Log $(date) ----" >> "$log_file"

# Add cron jobs for each folder
for folder in "${folders[@]}"; do
    # Ensure the folder exists
    if [ -d "$folder" ]; then
        # Convert relative paths to absolute paths
        abs_folder=$(readlink -f "$folder")
        # Add the cron job to clear the contents of the folder and log success/failure
        cron_command="$cron_frequency rm -rf ${abs_folder}/* && echo \"[$(date)] Success: Cleared $abs_folder\" >> $log_file || echo \"[$(date)] Failure: Could not clear $abs_folder\" >> $log_file"
        echo "$cron_command" >> current_cron_jobs
        echo "Added weekly cron job for folder: $abs_folder" >> "$log_file"
    else
        echo "Warning: Folder $folder does not exist." >> "$log_file"
    fi
done

# Install new cron jobs
crontab current_cron_jobs

# Clean up
rm current_cron_jobs

# Log completion
echo "Cron jobs installed. See log for details." >> "$log_file"
echo "----------------------------------------" >> "$log_file"
echo "Weekly cron jobs added, log written to $log_file"

# Check if anacron is installed, and install if necessary
if ! command -v anacron &> /dev/null
then
    echo "Anacron not found. Installing..."
    sudo apt-get update
    sudo apt-get install -y anacron
    echo "Anacron installed successfully." >> "$log_file"
else
    echo "Anacron is already installed." >> "$log_file"
fi

# Ensure the script adds anacron functionality if it's not already in /etc/anacrontab
anacron_task="7 5 weekly_cleanup /bin/bash ${script_dir}/add_clear_cron.sh"

if ! grep -Fxq "$anacron_task" /etc/anacrontab
then
    echo "Adding job to /etc/anacrontab..." >> "$log_file"
    echo "$anacron_task" | sudo tee -a /etc/anacrontab
    echo "Job added to /etc/anacrontab: $anacron_task" >> "$log_file"
else
    echo "Anacron task already exists in /etc/anacrontab." >> "$log_file"
fi

# Confirmation message for terminal
echo "Setup completed. Weekly cleanup job added to cron and anacron (if possible). Log written to $log_file"
