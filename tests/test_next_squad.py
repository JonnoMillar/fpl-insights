"""Owned-XI selection and transfer-preview boundaries; no network."""
import unittest
from copy import copy
from types import SimpleNamespace
from unittest.mock import patch

import next_squad
import cards_squad
from next_action import choose, explain_move
from tests.test_cv_readiness import make_reports
from tests.test_transfers import full_fifteen

class NextSquadTests(unittest.TestCase):
    def setUp(self):
        self.ctx,self.reports,self.scores=make_reports(full_fifteen())

    def test_optimises_owned_fifteen_without_spending_budget(self):
        self.scores[1]['total']=50
        self.reports[0].price=50
        selected=next_squad.select(self.reports,self.scores)
        self.assertEqual(len(selected['xi']),11)
        self.assertEqual(len(selected['bench']),4)
        self.assertEqual(selected['captain'],1)
        self.assertIn(1,[r.element['id'] for r in selected['xi']])
        self.assertNotEqual(selected['captain'],selected['vice'])
        self.assertEqual(selected['bench'][0].pos,'GKP')

    def test_missing_forecast_is_not_a_confirmed_blank(self):
        del self.scores[1]
        self.assertIsNone(next_squad.select(self.reports,self.scores))
        self.assertIsNotNone(next_squad.select(self.reports,self.scores,blank_ids={1}))

    def test_illegal_squad_is_withheld(self):
        self.assertIsNone(next_squad.select(self.reports[:-1],self.scores))
        for r in self.reports[2:6]:
            r.element['team']='C1'
        self.assertIsNone(next_squad.select(self.reports,self.scores))

    def incoming(self,old,pid,price):
        r=copy(old);r.element=dict(old.element,id=pid,now_cost=round(price*10),team='NEW');r.price=price
        return r

    def test_pair_uses_one_budget_and_recovered_selling_values(self):
        first,second=self.reports[2:4]
        incoming=[self.incoming(first,98,6),self.incoming(second,99,6)]
        moves=[{'out':first,'in':incoming[0].element},{'out':second,'in':incoming[1].element}]
        sells={first.element['id']:5,second.element['id']:5}
        self.assertIsNone(next_squad.apply_transfers(self.reports,incoming,moves,1.5,sells))
        result=next_squad.apply_transfers(self.reports,incoming,moves,2,sells)
        self.assertEqual(len(result),15)
        self.assertTrue({98,99}.issubset({r.element['id'] for r in result}))
        self.assertIsNone(next_squad.apply_transfers(self.reports,incoming,moves,10,None))

    def test_duplicate_and_wrong_position_moves_are_rejected(self):
        outgoing=self.reports[2];incoming=self.incoming(outgoing,98,5)
        move={'out':outgoing,'in':incoming.element}
        self.assertIsNone(next_squad.apply_transfers(self.reports,[incoming],[move,move],10,{outgoing.element['id']:5}))
        incoming.pos='MID'
        self.assertIsNone(next_squad.apply_transfers(self.reports,[incoming],[move],10,{outgoing.element['id']:5}))

    def test_preview_reselects_the_xi_and_its_captain(self):
        outgoing=self.reports[2]
        incoming=self.incoming(outgoing,98,5)
        scores=dict(self.scores)
        scores[98]={'total':50}
        changed=next_squad.apply_transfers(self.reports,[incoming],
            [{'out':outgoing,'in':incoming.element}],0,{outgoing.element['id']:5})
        team=next_squad.select(changed,scores)
        self.assertEqual(team['captain'],98)
        self.assertNotIn(outgoing.element['id'],[r.element['id'] for r in team['xi']+team['bench']])

    def test_incoming_cards_explain_highlight_and_keep_blank_distinct(self):
        r=SimpleNamespace(element=self.reports[2].element, pos='DEF', team='C3',
                          name='New defender',price=5,availability=(None,''))
        html=cards_squad.pick_card(r,self.ctx,{}, {},r.element['id'],None,{}, {},8,
                                  ep={'total':0},incoming=True)
        self.assertIn('suggested incoming transfer',html)
        self.assertIn('incoming-badge',html)
        self.assertIn('title="Captain"',html)
        self.assertIn('Blank',html)
        self.assertIn('0.0<small>xP</small>',html)
        self.ctx.fixtures=[{'event':8,'team_h':r.element['team'],'team_a':'OTHER'}]
        html=cards_squad.pick_card(r,self.ctx,{}, {},None,None,{}, {},8)
        self.assertIn('Unavailable',html)
        self.assertNotIn('>Blank<',html)

    def test_next_fixture_separates_opponent_and_position_metric(self):
        r=SimpleNamespace(element=self.reports[2].element, pos='DEF', team='C3',
                          name='Defender',price=5,availability=(None,''))
        self.ctx.fixtures=[{'event':8,'team_h':r.element['team'],'team_a':'OTHER'}]
        fixture={'opp':'E<V','home':True,'cs':45.6,'xg':1.75}
        with patch('cards_squad.ticker._rows_for',return_value=[fixture]):
            html=cards_squad.pick_card(r,self.ctx,{}, {},None,None,{}, {},8,ep={'total':5})
            self.assertIn('E&lt;V <small>(H)</small>',html)
            self.assertIn('<span>CS</span> <b>46%</b>',html)
            self.assertIn('Team clean-sheet chance',html)
            self.assertNotIn('<span>Team xG</span>',html)
            r.pos='FWD'
            fixture['home']=False
            html=cards_squad.pick_card(r,self.ctx,{}, {},None,None,{}, {},8,ep={'total':5})
            self.assertIn('E&lt;V <small>(A)</small>',html)
            self.assertIn('<span>Team xG</span> <b>1.75</b>',html)
            self.assertIn('Expected team goals',html)

    def test_week_total_counts_the_selected_captain_and_chips(self):
        team=next_squad.select(self.reports,self.scores)
        base=sum(self.scores[r.element['id']]['total'] for r in team['xi'])
        cap=self.scores[team['captain']]['total']
        bench=sum(self.scores[r.element['id']]['total'] for r in team['bench'])
        self.assertAlmostEqual(next_squad.projected_total(team,self.scores),base+cap)
        self.assertAlmostEqual(next_squad.projected_total(team,self.scores,chip='3xc'),base+2*cap)
        self.assertAlmostEqual(next_squad.projected_total(team,self.scores,chip='bboost'),base+bench+cap)
        self.assertIsNone(next_squad.projected_total(team,self.scores,chip='freehit'))
        changed=dict(team,captain=team['vice'])
        self.assertAlmostEqual(next_squad.projected_total(changed,self.scores),base+self.scores[team['vice']]['total'])

    def test_week_total_withholds_missing_data_but_accepts_a_confirmed_blank(self):
        team=next_squad.select(self.reports,self.scores)
        missing=team['xi'][0].element['id']
        scores={pid:score for pid,score in self.scores.items() if pid!=missing}
        self.assertIsNone(next_squad.projected_total(team,scores))
        self.assertIsNotNone(next_squad.projected_total(team,scores,blank_ids={missing}))
        self.assertIsNone(next_squad.projected_total(None,scores))
        self.assertIsNone(next_squad.projected_total(dict(team,captain=-1),self.scores))
        missing_bench=team['bench'][0].element['id']
        scores={pid:score for pid,score in self.scores.items() if pid!=missing_bench}
        self.assertIsNotNone(next_squad.projected_total(team,scores))
        self.assertIsNone(next_squad.projected_total(team,scores,chip='bboost'))
        self.assertIsNotNone(next_squad.projected_total(team,scores,blank_ids={missing_bench},chip='bboost'))

    def test_transfer_explanation_uses_real_form_and_flags_tough_fixtures(self):
        old=self.reports[2]
        old.element.update(web_name='Old',form='2.0',minutes=600,expected_goal_involvements_per_90=.2)
        new=dict(old.element,web_name='New',form='6.0')
        ctx=SimpleNamespace(next_fixtures=lambda *a,**k:[('OPP',False,4,8)],
                            teams={'OPP':{'name':'Liverpool'}},team_name=lambda tid:tid)
        text=explain_move({'out':old,'in':new},ctx,8)
        self.assertIn('form 6.0',text)
        self.assertIn('Liverpool away is a tough start',text)
        self.assertNotIn('kinder',text)

    def test_transfer_explanation_qualifies_small_samples_and_injury_doubts(self):
        old=self.reports[2]
        old.element.update(web_name='Old',minutes=600,expected_goal_involvements_per_90=.1)
        new=dict(old.element,web_name='New',minutes=180,expected_goal_involvements_per_90=.7,status='d')
        ctx=SimpleNamespace(next_fixtures=lambda *a,**k:[('OPP',True,2,8)],
                            teams={'OPP':{'name':'Everton'}},team_name=lambda tid:tid)
        text=explain_move({'out':old,'in':new},ctx,8)
        self.assertIn('0.70 expected goal involvements per 90',text)
        self.assertIn('only 180 minutes',text)
        self.assertIn('flagged as a doubt',text)
        self.assertIn('kinder fixture against Everton at home',text)
        new.update(minutes=600)
        del old.element['expected_goal_involvements_per_90']
        self.assertNotIn("against Old's 0.00",explain_move({'out':old,'in':new},ctx,8))

    def test_action_exposes_only_the_moves_it_actually_selects(self):
        old=self.reports[2];incoming=self.incoming(old,98,5)
        row={'out':old,'in':incoming.element,'gain':10}
        self.assertEqual(choose([row],[],1,True,8)['moves'],[row])
        self.assertEqual(choose([row],[],1,True,8)['projected_gain'],10)
        self.assertEqual(choose([row],[],1,True,8)['horizon'],5)
        self.assertEqual(choose([row],[],0,True,8)['projected_gain'],6)
        self.assertEqual(choose([row],[],1,False,8).get('moves',[]),[])
        chip=('3xc','Triple Captain',{'gw':8,'ep':10,'confidence':'strong'})
        action=choose([row],[],1,True,8,[chip],{})
        self.assertEqual(action['chip'],'3xc')
        self.assertEqual(action.get('moves',[]),[])
        self.assertNotIn('projected_gain',action)
