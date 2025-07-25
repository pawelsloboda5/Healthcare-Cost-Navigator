/**
 * Healthcare Cost Navigator - Frontend JavaScript
 * Handles AI assistant, provider search, cost analysis, and system status
 */

const API_BASE = 'http://localhost:8000/api/v1';
let lastApiResponse = null;

// ====================================================================
// UTILITY FUNCTIONS
// ====================================================================

function showLoading() {
    document.getElementById('loading').style.display = 'block';
}

function hideLoading() {
    document.getElementById('loading').style.display = 'none';
}

function updateRawData(data) {
    lastApiResponse = data;
    if (document.getElementById('rawDataContainer').style.display !== 'none') {
        document.getElementById('rawData').textContent = JSON.stringify(data, null, 2);
    }
}

function handleApiError(error, context) {
    console.error(`Error in ${context}:`, error);
    return `Error in ${context}: ${error.message || error}`;
}

function formatCurrency(amount) {
    if (!amount) return 'N/A';
    const num = parseFloat(amount);
    return '$' + num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatRating(rating) {
    if (!rating) return 'N/A';
    return parseFloat(rating).toFixed(1) + '/10';
}

// ====================================================================
// AI ASSISTANT FUNCTIONS
// ====================================================================

async function askAI() {
    const question = document.getElementById('aiQuestion').value.trim();
    if (!question) {
        alert('Please enter a question');
        return;
    }

    showLoading();
    try {
        const response = await fetch(`${API_BASE}/ask`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                question: question,
                use_template_matching: true
            })
        });

        const data = await response.json();
        updateRawData(data);

        if (data.success) {
            displayAIResponse(data);
        } else {
            document.getElementById('aiAnswer').innerHTML = `<strong>Error:</strong> ${data.answer}`;
            document.getElementById('aiDetails').innerHTML = '';
        }
    } catch (error) {
        document.getElementById('aiAnswer').innerHTML = handleApiError(error, 'AI Assistant');
        document.getElementById('aiDetails').innerHTML = '';
    } finally {
        hideLoading();
    }
}

function displayAIResponse(data) {
    const answerDiv = document.getElementById('aiAnswer');
    const detailsDiv = document.getElementById('aiDetails');

    // Display the natural language answer
    answerDiv.innerHTML = `<strong>Answer:</strong> ${data.answer}`;

    // Display technical details
    let details = '<h4>Technical Details:</h4>';
    
    if (data.template_used) {
        details += `<p><strong>Template Used:</strong> #${data.template_used} (Confidence: ${(data.confidence_score * 100).toFixed(1)}%)</p>`;
    }
    
    if (data.sql_query) {
        details += `<p><strong>SQL Query:</strong></p><pre>${data.sql_query}</pre>`;
    }
    
    if (data.execution_time_ms) {
        details += `<p><strong>Execution Time:</strong> ${data.execution_time_ms}ms</p>`;
    }

    // Display results in a table if available
    if (data.results && data.results.length > 0) {
        details += '<h4>Results:</h4>';
        details += createResultsTable(data.results);
    }

    detailsDiv.innerHTML = details;
}

function setQuestion(question) {
    document.getElementById('aiQuestion').value = question;
}

function clearAIResults() {
    document.getElementById('aiQuestion').value = '';
    document.getElementById('aiAnswer').innerHTML = '';
    document.getElementById('aiDetails').innerHTML = '';
}

// ====================================================================
// PROVIDER SEARCH FUNCTIONS
// ====================================================================

async function searchProviders(event) {
    if (event) event.preventDefault();

    const criteria = {
        state: document.getElementById('searchState').value.trim() || null,
        city: document.getElementById('searchCity').value.trim() || null,
        drg_code: document.getElementById('searchDrg').value.trim() || null,
        min_rating: parseFloat(document.getElementById('searchRating').value) || null,
        max_cost: parseFloat(document.getElementById('searchCost').value) || null,
        limit: parseInt(document.getElementById('searchLimit').value) || 10
    };

    showLoading();
    try {
        const response = await fetch(`${API_BASE}/providers/search`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(criteria)
        });

        const data = await response.json();
        updateRawData(data);
        
        if (!response.ok) {
            throw new Error(data.detail || `HTTP ${response.status}`);
        }
        
        displayProviderResults(data, 'Provider Search Results');
    } catch (error) {
        document.getElementById('providerList').innerHTML = handleApiError(error, 'Provider Search');
    } finally {
        hideLoading();
    }
}

async function getCheapestProviders(drgCode) {
    showLoading();
    try {
        const response = await fetch(`${API_BASE}/providers/cheapest/${drgCode}?limit=10`);
        const data = await response.json();
        updateRawData(data);
        
        if (!response.ok) {
            throw new Error(data.detail || `HTTP ${response.status}`);
        }
        
        displayProviderResults(data, `Cheapest Providers for DRG ${drgCode}`);
    } catch (error) {
        document.getElementById('providerList').innerHTML = handleApiError(error, 'Cheapest Providers');
    } finally {
        hideLoading();
    }
}

async function getHighestRated() {
    showLoading();
    try {
        const response = await fetch(`${API_BASE}/providers/highest-rated?limit=10`);
        const data = await response.json();
        updateRawData(data);
        
        if (!response.ok) {
            throw new Error(data.detail || `HTTP ${response.status}`);
        }
        
        displayProviderResults(data, 'Highest Rated Providers');
    } catch (error) {
        document.getElementById('providerList').innerHTML = handleApiError(error, 'Highest Rated Providers');
    } finally {
        hideLoading();
    }
}

async function getVolumeLeaders(drgCode) {
    showLoading();
    try {
        const response = await fetch(`${API_BASE}/providers/volume-leaders/${drgCode}?limit=10`);
        const data = await response.json();
        updateRawData(data);
        
        if (!response.ok) {
            throw new Error(data.detail || `HTTP ${response.status}`);
        }
        
        displayProviderResults(data, `Volume Leaders for DRG ${drgCode}`);
    } catch (error) {
        document.getElementById('providerList').innerHTML = handleApiError(error, 'Volume Leaders');
    } finally {
        hideLoading();
    }
}

function displayProviderResults(providers, title) {
    const listDiv = document.getElementById('providerList');
    
    if (!providers || providers.length === 0) {
        listDiv.innerHTML = `<h4>${title}</h4><p>No providers found matching your criteria.</p>`;
        return;
    }

    let html = `<h4>${title} (${providers.length} results)</h4>`;
    html += createProviderTable(providers);
    listDiv.innerHTML = html;
}

function createProviderTable(providers) {
    let html = '<table border="1" width="100%" cellpadding="8" cellspacing="0">';
    html += '<tr style="background-color: #f0f0f0;">';
    html += '<th style="text-align: left; padding: 8px;">Provider Name</th>';
    html += '<th style="text-align: left; padding: 8px;">Procedure</th>';
    html += '<th style="text-align: left; padding: 8px;">Location</th>';
    html += '<th style="text-align: left; padding: 8px;">Cost</th>';
    html += '<th style="text-align: left; padding: 8px;">Volume</th>';
    html += '<th style="text-align: left; padding: 8px;">Rating</th>';
    html += '</tr>';

    providers.forEach((provider, index) => {
        const bgColor = index % 2 === 0 ? '#ffffff' : '#f9f9f9';
        html += `<tr style="background-color: ${bgColor};">`;
        
        // Provider Name
        html += `<td style="padding: 8px; font-weight: bold; vertical-align: top;">`;
        html += `${provider.provider_name}`;
        if (provider.provider_id) {
            html += `<br><small style="color: #666; font-weight: normal;">ID: ${provider.provider_id}</small>`;
        }
        html += '</td>';
        
        // Procedure Information
        html += `<td style="padding: 8px; vertical-align: top; max-width: 200px;">`;
        if (provider.drg_code && provider.drg_description) {
            html += `<strong>DRG ${provider.drg_code}</strong><br>`;
            let description = provider.drg_description;
            if (description.length > 40) {
                description = description.substring(0, 40) + '...';
            }
            html += `<small style="font-style: italic;">${description}</small>`;
        } else if (provider.drg_code) {
            html += `DRG ${provider.drg_code}`;
        } else {
            html += '<span style="color: #888; font-style: italic;">N/A</span>';
        }
        html += '</td>';
        
        // Location
        html += `<td style="padding: 8px; vertical-align: top;">`;
        html += `${provider.provider_city}, ${provider.provider_state}`;
        if (provider.provider_zip_code) {
            html += `<br><small style="color: #666;">${provider.provider_zip_code}</small>`;
        }
        html += '</td>';
        
        // Cost
        html += `<td style="padding: 8px; text-align: right; font-weight: bold; vertical-align: top;">`;
        if (provider.average_covered_charges) {
            html += `${formatCurrency(provider.average_covered_charges)}`;
            if (provider.average_medicare_payments) {
                html += `<br><small style="color: #666; font-weight: normal;">Medicare: ${formatCurrency(provider.average_medicare_payments)}</small>`;
            }
        } else {
            html += '<span style="color: #888; font-style: italic;">N/A</span>';
        }
        html += '</td>';
        
        // Volume
        html += `<td style="padding: 8px; text-align: center; vertical-align: top;">`;
        html += provider.total_discharges || '<span style="color: #888; font-style: italic;">N/A</span>';
        html += '</td>';
        
        // Rating
        html += `<td style="padding: 8px; text-align: center; vertical-align: top;">`;
        if (provider.overall_rating) {
            html += `${formatRating(provider.overall_rating)}`;
            if (provider.quality_rating) {
                html += `<br><small style="color: #666;">Quality: ${formatRating(provider.quality_rating)}</small>`;
            }
        } else {
            html += '<span style="color: #888; font-style: italic;">N/A</span>';
        }
        html += '</td>';
        
        html += '</tr>';
    });

    html += '</table>';
    return html;
}

function clearProviderSearch() {
    document.getElementById('searchState').value = '';
    document.getElementById('searchCity').value = '';
    document.getElementById('searchDrg').value = '';
    document.getElementById('searchRating').value = '';
    document.getElementById('searchCost').value = '';
    document.getElementById('searchLimit').value = '10';
    document.getElementById('providerList').innerHTML = '';
}

// ====================================================================
// COST ANALYSIS FUNCTIONS
// ====================================================================

async function analyzeCosts() {
    const drgCode = document.getElementById('analysisCode').value.trim();
    const state = document.getElementById('analysisState').value.trim();
    
    if (!drgCode) {
        alert('Please enter a DRG code');
        return;
    }

    showLoading();
    try {
        let url = `${API_BASE}/analysis/costs/${drgCode}`;
        if (state) {
            url += `?state=${state}`;
        }

        const response = await fetch(url);
        const data = await response.json();
        updateRawData(data);
        displayCostAnalysis(data);
    } catch (error) {
        document.getElementById('costDetails').innerHTML = handleApiError(error, 'Cost Analysis');
    } finally {
        hideLoading();
    }
}

function displayCostAnalysis(analysis) {
    const detailsDiv = document.getElementById('costDetails');
    
    if (!analysis || analysis.error) {
        detailsDiv.innerHTML = `<p>Error: ${analysis?.detail || 'Cost analysis failed'}</p>`;
        return;
    }

    let html = `<h4>Cost Analysis for DRG ${analysis.drg_code}</h4>`;
    
    if (analysis.drg_description) {
        html += `<p><strong>Procedure:</strong> ${analysis.drg_description}</p>`;
    }
    
    html += '<table border="1" width="100%">';
    html += '<tr><th>Metric</th><th>Value</th></tr>';
    html += `<tr><td>Average Cost</td><td>${formatCurrency(analysis.average_cost)}</td></tr>`;
    html += `<tr><td>Median Cost</td><td>${formatCurrency(analysis.median_cost)}</td></tr>`;
    html += `<tr><td>Cost Variance</td><td>${formatCurrency(analysis.cost_variance)}</td></tr>`;
    html += `<tr><td>Total Providers</td><td>${analysis.total_providers}</td></tr>`;
    html += '</table>';

    if (analysis.cheapest_provider) {
        html += '<h5>Cheapest Provider:</h5>';
        html += `<p><strong>${analysis.cheapest_provider.provider_name}</strong><br>`;
        html += `${analysis.cheapest_provider.provider_city}, ${analysis.cheapest_provider.provider_state}<br>`;
        html += `Cost: ${formatCurrency(analysis.cheapest_provider.average_covered_charges)}</p>`;
    }

    if (analysis.most_expensive_provider) {
        html += '<h5>Most Expensive Provider:</h5>';
        html += `<p><strong>${analysis.most_expensive_provider.provider_name}</strong><br>`;
        html += `${analysis.most_expensive_provider.provider_city}, ${analysis.most_expensive_provider.provider_state}<br>`;
        html += `Cost: ${formatCurrency(analysis.most_expensive_provider.average_covered_charges)}</p>`;
    }

    detailsDiv.innerHTML = html;
}

// ====================================================================
// SYSTEM STATUS FUNCTIONS
// ====================================================================

async function checkHealth() {
    showLoading();
    try {
        const response = await fetch(`${API_BASE}/health`);
        const data = await response.json();
        updateRawData(data);
        
        document.getElementById('healthStatus').innerHTML = 
            `<h4>API Health Status</h4><p><strong>Status:</strong> ${data.status}<br><strong>Service:</strong> ${data.service}</p>`;
    } catch (error) {
        document.getElementById('healthStatus').innerHTML = 
            `<h4>API Health Status</h4><p><strong>Error:</strong> ${error.message}</p>`;
    } finally {
        hideLoading();
    }
}

async function getTemplateStats() {
    showLoading();
    try {
        const response = await fetch(`${API_BASE}/template-stats`);
        const data = await response.json();
        updateRawData(data);
        
        let html = '<h4>Template Statistics</h4>';
        if (data.template_statistics) {
            html += '<table border="1">';
            Object.entries(data.template_statistics).forEach(([key, value]) => {
                html += `<tr><td>${key}</td><td>${value}</td></tr>`;
            });
            html += '</table>';
        } else {
            html += '<p>No template statistics available</p>';
        }
        
        document.getElementById('templateStats').innerHTML = html;
    } catch (error) {
        document.getElementById('templateStats').innerHTML = 
            `<h4>Template Statistics</h4><p><strong>Error:</strong> ${error.message}</p>`;
    } finally {
        hideLoading();
    }
}

// ====================================================================
// UTILITY DISPLAY FUNCTIONS
// ====================================================================

function createResultsTable(results) {
    if (!results || results.length === 0) {
        return '<p>No results found.</p>';
    }

    // Define preferred column order for better readability
    const columnOrder = [
        'provider_name',
        'drg_description', 
        'average_covered_charges',
        'average_total_payments',
        'average_medicare_payments',
        'total_discharges',
        'provider_city',
        'provider_state',
        'overall_rating',
        'quality_rating'
    ];
    
    const availableKeys = Object.keys(results[0]);
    
    // Use preferred order for existing columns, then add any remaining columns
    const orderedKeys = columnOrder.filter(key => availableKeys.includes(key))
                                  .concat(availableKeys.filter(key => !columnOrder.includes(key)));
    
    let html = '<table border="1" width="100%" cellpadding="8" cellspacing="0">';
    
    // Header with better formatting
    html += '<tr style="background-color: #f0f0f0;">';
    orderedKeys.forEach(key => {
        let headerName = key.replace(/_/g, ' ').toUpperCase();
        
        // Special header names for better readability
        if (key === 'drg_description') headerName = 'PROCEDURE';
        if (key === 'average_covered_charges') headerName = 'AVERAGE COST';
        if (key === 'average_total_payments') headerName = 'TOTAL PAYMENTS';
        if (key === 'average_medicare_payments') headerName = 'MEDICARE PAYMENTS';
        if (key === 'total_discharges') headerName = 'VOLUME';
        if (key === 'overall_rating') headerName = 'RATING';
        
        html += `<th style="text-align: left; padding: 8px;">${headerName}</th>`;
    });
    html += '</tr>';
    
    // Data rows with enhanced formatting
    results.forEach((row, index) => {
        const bgColor = index % 2 === 0 ? '#ffffff' : '#f9f9f9';
        html += `<tr style="background-color: ${bgColor};">`;
        
        orderedKeys.forEach(key => {
            let value = row[key];
            let cellStyle = 'padding: 8px; vertical-align: top;';
            
            // Format specific columns
            if (key.includes('charge') || key.includes('payment') || key.includes('cost')) {
                value = formatCurrency(value);
                cellStyle += ' text-align: right; font-weight: bold;';
            } else if (key.includes('rating')) {
                value = formatRating(value);
                cellStyle += ' text-align: center;';
            } else if (key === 'drg_description') {
                // Special formatting for procedure descriptions
                cellStyle += ' font-style: italic; max-width: 200px;';
                if (value && value.length > 50) {
                    value = value.substring(0, 50) + '...';
                }
            } else if (key === 'provider_name') {
                cellStyle += ' font-weight: bold;';
            } else if (key === 'total_discharges') {
                cellStyle += ' text-align: center;';
            } else if (value === null || value === undefined) {
                value = 'N/A';
                cellStyle += ' color: #888; font-style: italic;';
            }
            
            html += `<td style="${cellStyle}">${value}</td>`;
        });
        html += '</tr>';
    });
    
    html += '</table>';
    return html;
}

function toggleRawData() {
    const container = document.getElementById('rawDataContainer');
    const dataDiv = document.getElementById('rawData');
    
    if (container.style.display === 'none') {
        container.style.display = 'block';
        if (lastApiResponse) {
            dataDiv.textContent = JSON.stringify(lastApiResponse, null, 2);
        } else {
            dataDiv.textContent = 'No API response data available yet.';
        }
    } else {
        container.style.display = 'none';
    }
}

// ====================================================================
// INITIALIZATION
// ====================================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('Healthcare Cost Navigator loaded');
    
    // Auto-check health on load
    checkHealth();
    
    // Add Enter key support for AI assistant
    document.getElementById('aiQuestion').addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            askAI();
        }
    });
    
    console.log('Frontend initialization complete');
});
