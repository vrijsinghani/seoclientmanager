from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Crew, CrewExecution, Task, Agent

@login_required
def crew_kanban(request, crew_id):
    crew = Crew.objects.get(id=crew_id)
    
    # Mock data organized by tasks
    context = {
        'crew': crew,
        'tasks': [
            {
                'id': 1,
                'name': 'Keyword Research',
                'status': 'in_progress',
                'stages': {
                    'task_start': {
                        'title': 'Initial Keyword Research Setup',
                        'content': 'Starting comprehensive keyword analysis for client website',
                        'agent': 'Research Manager'
                    },
                    'thinking': {
                        'title': 'Keyword Strategy Development',
                        'content': 'Planning comprehensive keyword research approach',
                        'thought_process': 'Need to focus on long-tail keywords with high conversion potential'
                    },
                    'tool_usage': {
                        'title': 'Running SEMrush Analysis',
                        'tool': 'SEMrush API',
                        'input': 'Domain: example.com, Industry: Technology, Location: Global'
                    },
                    'tool_results': {
                        'title': 'Keyword Research Results',
                        'tool': 'SEMrush API',
                        'result': 'Identified 500+ keywords: 150 high-priority, 250 medium-priority, 100 long-tail'
                    },
                    'human_input': {
                        'title': 'Keyword Priority Review',
                        'prompt': 'Please review and approve the keyword priority list',
                        'context': 'We have categorized 500 keywords based on search volume and competition'
                    },
                    'completion': {
                        'title': 'Keyword Strategy Finalized',
                        'output': 'Comprehensive keyword targeting plan with 500 categorized keywords',
                        'reasoning': 'Balanced approach focusing on quick wins and long-term growth'
                    }
                }
            },
            {
                'id': 2,
                'name': 'Technical SEO Audit',
                'status': 'in_progress',
                'stages': {
                    'task_start': {
                        'title': 'Technical Audit Initialization',
                        'content': 'Beginning comprehensive technical SEO analysis',
                        'agent': 'Technical SEO Specialist'
                    },
                    'thinking': {
                        'title': 'Technical Assessment Strategy',
                        'content': 'Planning technical audit methodology',
                        'thought_process': 'Focus on core web vitals, indexing, and site architecture'
                    },
                    'tool_usage': {
                        'title': 'Running Technical Analysis',
                        'tool': 'Screaming Frog SEO Spider',
                        'input': 'URL: example.com, Crawl Depth: Full Site'
                    },
                    'tool_results': {
                        'title': 'Technical Audit Results',
                        'tool': 'Screaming Frog SEO Spider',
                        'result': 'Found 45 critical issues across multiple technical aspects'
                    },
                    'human_input': {
                        'title': 'Technical Issues Priority',
                        'prompt': 'Please confirm the prioritization of technical fixes',
                        'context': '45 issues found, need to prioritize based on impact'
                    },
                    'completion': {
                        'title': 'Technical Audit Complete',
                        'output': 'Detailed technical optimization plan with prioritized fixes',
                        'reasoning': 'Addressing critical issues first for maximum impact'
                    }
                }
            },
            {
                'id': 3,
                'name': 'Content Gap Analysis',
                'status': 'in_progress',
                'stages': {
                    'task_start': {
                        'title': 'Content Analysis Setup',
                        'content': 'Initiating content gap analysis process',
                        'agent': 'Content Strategist'
                    },
                    'thinking': {
                        'title': 'Content Strategy Planning',
                        'content': 'Evaluating content opportunities',
                        'thought_process': 'Identify underserved topics with high search potential'
                    },
                    'tool_usage': {
                        'title': 'Content Analysis',
                        'tool': 'ContentKing API',
                        'input': 'URL: example.com/blog, Content Type: All Pages'
                    },
                    'tool_results': {
                        'title': 'Content Analysis Results',
                        'tool': 'ContentKing API',
                        'result': 'Analyzed 200 pages: 50 need updates, 30 consolidation, 100 new opportunities'
                    },
                    'human_input': {
                        'title': 'Content Strategy Review',
                        'prompt': 'Review proposed content calendar and topics',
                        'context': '6-month content plan based on gap analysis'
                    },
                    'completion': {
                        'title': 'Content Strategy Finalized',
                        'output': '6-month content calendar with 100 planned pieces',
                        'reasoning': 'Comprehensive coverage of identified content gaps'
                    }
                }
            }
        ]
    }
    return render(request, 'agents/crew_kanban.html', context)
