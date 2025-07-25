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
    let html = '<div style="overflow-x: auto;">';
    html += '<table style="width: 100%; border-collapse: collapse; margin: 20px 0; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">';
    html += '<thead>';
    html += '<tr style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">';
    html += '<th style="text-align: left; padding: 15px; font-weight: 600;">Provider Name</th>';
    html += '<th style="text-align: left; padding: 15px; font-weight: 600;">Procedure</th>';
    html += '<th style="text-align: left; padding: 15px; font-weight: 600;">Location</th>';
    html += '<th style="text-align: left; padding: 15px; font-weight: 600;">Cost</th>';
    html += '<th style="text-align: center; padding: 15px; font-weight: 600;">Volume</th>';
    html += '<th style="text-align: center; padding: 15px; font-weight: 600;">Rating</th>';
    html += '</tr>';
    html += '</thead>';
    html += '<tbody>';

    providers.forEach((provider, index) => {
        const bgColor = index % 2 === 0 ? '#ffffff' : '#f8f9fa';
        html += `<tr style="background-color: ${bgColor}; transition: background-color 0.3s ease;" onmouseover="this.style.backgroundColor='#e9ecef'" onmouseout="this.style.backgroundColor='${bgColor}'">`;
        
        // Provider Name
        html += `<td style="padding: 15px; font-weight: 600; vertical-align: top; border-bottom: 1px solid #dee2e6;">`;
        html += `<div style="color: #2c3e50;">${provider.provider_name}</div>`;
        if (provider.provider_id) {
            html += `<small style="color: #6c757d; font-weight: normal;">ID: ${provider.provider_id}</small>`;
        }
        html += '</td>';
        
        // Procedure Information
        html += `<td style="padding: 15px; vertical-align: top; max-width: 250px; border-bottom: 1px solid #dee2e6;">`;
        if (provider.drg_code && provider.drg_description) {
            html += `<div style="font-weight: 600; color: #495057; margin-bottom: 5px;">DRG ${provider.drg_code}</div>`;
            let description = provider.drg_description;
            if (description.length > 50) {
                description = description.substring(0, 50) + '...';
            }
            html += `<small style="color: #6c757d; font-style: italic;">${description}</small>`;
        } else if (provider.drg_code) {
            html += `<span style="font-weight: 600; color: #495057;">DRG ${provider.drg_code}</span>`;
        } else if (provider.procedure_count) {
            // Show aggregate data info
            html += `<div style="font-weight: 600; color: #495057; margin-bottom: 5px;">All Procedures</div>`;
            html += `<small style="color: #6c757d; font-style: italic;">${provider.procedure_count} different procedures</small>`;
        } else {
            html += '<span style="color: #adb5bd; font-style: italic;">N/A</span>';
        }
        html += '</td>';
        
        // Location
        html += `<td style="padding: 15px; vertical-align: top; border-bottom: 1px solid #dee2e6;">`;
        html += `<div style="font-weight: 600; color: #495057;">${provider.provider_city}, ${provider.provider_state}</div>`;
        if (provider.provider_zip_code) {
            html += `<small style="color: #6c757d;">${provider.provider_zip_code}</small>`;
        }
        html += '</td>';
        
        // Cost
        html += `<td style="padding: 15px; text-align: right; vertical-align: top; border-bottom: 1px solid #dee2e6;">`;
        if (provider.average_covered_charges) {
            const costLabel = provider.drg_code ? 'Procedure Cost:' : 'Avg Cost:';
            html += `<div style="font-weight: 700; color: #28a745; font-size: 1.1em;">${formatCurrency(provider.average_covered_charges)}</div>`;
            if (provider.average_medicare_payments) {
                html += `<small style="color: #6c757d;">Medicare: ${formatCurrency(provider.average_medicare_payments)}</small>`;
            }
            if (!provider.drg_code && provider.procedure_count) {
                html += `<br><small style="color: #6c757d; font-style: italic;">Across ${provider.procedure_count} procedures</small>`;
            }
        } else {
            html += '<span style="color: #adb5bd; font-style: italic;">N/A</span>';
        }
        html += '</td>';
        
        // Volume
        html += `<td style="padding: 15px; text-align: center; vertical-align: top; border-bottom: 1px solid #dee2e6;">`;
        if (provider.total_discharges) {
            html += `<span style="font-weight: 600; color: #495057;">${provider.total_discharges}</span>`;
            if (!provider.drg_code && provider.procedure_count) {
                html += `<br><small style="color: #6c757d; font-style: italic;">Total across all</small>`;
            }
        } else {
            html += '<span style="color: #adb5bd; font-style: italic;">N/A</span>';
        }
        html += '</td>';
        
        // Rating
        html += `<td style="padding: 15px; text-align: center; vertical-align: top; border-bottom: 1px solid #dee2e6;">`;
        if (provider.overall_rating) {
            const rating = parseFloat(provider.overall_rating);
            const ratingColor = rating >= 8 ? '#28a745' : rating >= 6 ? '#ffc107' : '#dc3545';
            html += `<div style="font-weight: 700; color: ${ratingColor}; font-size: 1.1em;">${formatRating(provider.overall_rating)}</div>`;
            if (provider.quality_rating) {
                html += `<small style="color: #6c757d;">Quality: ${formatRating(provider.quality_rating)}</small>`;
            }
        } else {
            html += '<span style="color: #adb5bd; font-style: italic;">N/A</span>';
        }
        html += '</td>';
        
        html += '</tr>';
    });

    html += '</tbody>';
    html += '</table>';
    html += '</div>';
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
        detailsDiv.innerHTML = `<div style="text-align: center; padding: 20px; color: #dc3545;">Error: ${analysis?.detail || 'Cost analysis failed'}</div>`;
        return;
    }

    let html = `<div style="background: white; padding: 20px; border-radius: 8px; border: 1px solid #dee2e6;">`;
    html += `<h4 style="color: #2c3e50; margin-bottom: 20px; font-size: 1.3em;">Cost Analysis for DRG ${analysis.drg_code}</h4>`;
    
    if (analysis.drg_description) {
        html += `<p style="color: #6c757d; font-style: italic; margin-bottom: 25px;"><strong>Procedure:</strong> ${analysis.drg_description}</p>`;
    }
    
    html += '<div style="overflow-x: auto;">';
    html += '<table style="width: 100%; border-collapse: collapse; margin: 20px 0; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">';
    html += '<thead>';
    html += '<tr style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">';
    html += '<th style="text-align: left; padding: 15px; font-weight: 600;">Metric</th>';
    html += '<th style="text-align: right; padding: 15px; font-weight: 600;">Value</th>';
    html += '</tr>';
    html += '</thead>';
    html += '<tbody>';
    
    const metrics = [
        { label: 'Average Cost', value: formatCurrency(analysis.average_cost), color: '#495057' },
        { label: 'Median Cost', value: formatCurrency(analysis.median_cost), color: '#495057' },
        { label: 'Cost Variance', value: formatCurrency(analysis.cost_variance), color: '#6c757d' },
        { label: 'Total Providers', value: analysis.total_providers, color: '#495057' }
    ];
    
    metrics.forEach((metric, index) => {
        const bgColor = index % 2 === 0 ? '#ffffff' : '#f8f9fa';
        html += `<tr style="background-color: ${bgColor};">`;
        html += `<td style="padding: 15px; font-weight: 600; color: #2c3e50; border-bottom: 1px solid #dee2e6;">${metric.label}</td>`;
        html += `<td style="padding: 15px; text-align: right; font-weight: 700; color: ${metric.color}; font-size: 1.1em; border-bottom: 1px solid #dee2e6;">${metric.value}</td>`;
        html += '</tr>';
    });
    
    html += '</tbody>';
    html += '</table>';
    html += '</div>';

    if (analysis.cheapest_provider) {
        html += '<div style="background: #d4edda; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #28a745;">';
        html += '<h5 style="color: #155724; margin-bottom: 10px;">💰 Cheapest Provider:</h5>';
        html += `<p style="color: #155724; margin: 0;"><strong>${analysis.cheapest_provider.provider_name}</strong><br>`;
        html += `${analysis.cheapest_provider.provider_city}, ${analysis.cheapest_provider.provider_state}<br>`;
        html += `<span style="font-weight: 700; font-size: 1.1em;">Cost: ${formatCurrency(analysis.cheapest_provider.cost)}</span></p>`;
        html += '</div>';
    }

    if (analysis.most_expensive_provider) {
        html += '<div style="background: #f8d7da; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #dc3545;">';
        html += '<h5 style="color: #721c24; margin-bottom: 10px;">💸 Most Expensive Provider:</h5>';
        html += `<p style="color: #721c24; margin: 0;"><strong>${analysis.most_expensive_provider.provider_name}</strong><br>`;
        html += `${analysis.most_expensive_provider.provider_city}, ${analysis.most_expensive_provider.provider_state}<br>`;
        html += `<span style="font-weight: 700; font-size: 1.1em;">Cost: ${formatCurrency(analysis.most_expensive_provider.cost)}</span></p>`;
        html += '</div>';
    }

    html += '</div>';
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
        return '<div style="text-align: center; padding: 20px; color: #6c757d; font-style: italic;">No results found.</div>';
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
    
    let html = '<div style="overflow-x: auto;">';
    html += '<table style="width: 100%; border-collapse: collapse; margin: 20px 0; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">';
    
    // Header with better formatting
    html += '<thead>';
    html += '<tr style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">';
    orderedKeys.forEach(key => {
        let headerName = key.replace(/_/g, ' ').toUpperCase();
        
        // Special header names for better readability
        if (key === 'drg_description') headerName = 'PROCEDURE';
        if (key === 'average_covered_charges') headerName = 'AVERAGE COST';
        if (key === 'average_total_payments') headerName = 'TOTAL PAYMENTS';
        if (key === 'average_medicare_payments') headerName = 'MEDICARE PAYMENTS';
        if (key === 'total_discharges') headerName = 'VOLUME';
        if (key === 'overall_rating') headerName = 'RATING';
        
        const textAlign = (key.includes('charge') || key.includes('payment') || key.includes('cost')) ? 'right' : 
                         (key.includes('rating') || key === 'total_discharges') ? 'center' : 'left';
        
        html += `<th style="text-align: ${textAlign}; padding: 15px; font-weight: 600;">${headerName}</th>`;
    });
    html += '</tr>';
    html += '</thead>';
    
    // Data rows with enhanced formatting
    html += '<tbody>';
    results.forEach((row, index) => {
        const bgColor = index % 2 === 0 ? '#ffffff' : '#f8f9fa';
        html += `<tr style="background-color: ${bgColor}; transition: background-color 0.3s ease;" onmouseover="this.style.backgroundColor='#e9ecef'" onmouseout="this.style.backgroundColor='${bgColor}'">`;
        
        orderedKeys.forEach(key => {
            let value = row[key];
            let cellStyle = 'padding: 15px; vertical-align: top; border-bottom: 1px solid #dee2e6;';
            
            // Format specific columns
            if (key.includes('charge') || key.includes('payment') || key.includes('cost')) {
                value = formatCurrency(value);
                cellStyle += ' text-align: right; font-weight: 700; color: #28a745; font-size: 1.1em;';
            } else if (key.includes('rating')) {
                const rating = parseFloat(value);
                const ratingColor = rating >= 8 ? '#28a745' : rating >= 6 ? '#ffc107' : '#dc3545';
                value = formatRating(value);
                cellStyle += ` text-align: center; font-weight: 700; color: ${ratingColor}; font-size: 1.1em;`;
            } else if (key === 'drg_description') {
                // Special formatting for procedure descriptions
                cellStyle += ' font-style: italic; max-width: 250px; color: #495057;';
                if (value && value.length > 60) {
                    value = value.substring(0, 60) + '...';
                }
            } else if (key === 'provider_name') {
                cellStyle += ' font-weight: 600; color: #2c3e50;';
            } else if (key === 'total_discharges') {
                cellStyle += ' text-align: center; font-weight: 600; color: #495057;';
            } else if (value === null || value === undefined) {
                value = 'N/A';
                cellStyle += ' color: #adb5bd; font-style: italic;';
            } else {
                cellStyle += ' color: #495057;';
            }
            
            html += `<td style="${cellStyle}">${value}</td>`;
        });
        html += '</tr>';
    });
    
    html += '</tbody>';
    html += '</table>';
    html += '</div>';
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
