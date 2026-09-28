import sys
from pathlib import Path
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from group_layouts import grouping_layouts

class GroupingTests(unittest.TestCase):
    def test_strong_communities_and_unlinked_are_preserved(self):
        edges=[]
        for group in ((0,1,2),(3,4,5)):
            for a in group:
                for b in group:
                    if a<b:edges.append({'s':a,'t':b,'r':-.95,'mi':1.2})
        edges.append({'s':2,'t':3,'r':.01,'mi':.001})
        data={'nodes':[{'id':str(i)} for i in range(7)],'edges':edges}
        results=grouping_layouts(data)
        for metric,layout in results.items():
            labels=layout['groups']; coords=np.array(layout['positions'])
            self.assertEqual(layout['unlinkedCount'],1)
            self.assertEqual(labels[6],-1)
            self.assertEqual(len(set(labels[:3])),1)
            self.assertEqual(len(set(labels[3:6])),1)
            self.assertNotEqual(labels[0],labels[3])
            self.assertTrue(np.isfinite(coords).all())
            within=np.mean([np.linalg.norm(coords[a]-coords[b]) for a,b in ((0,1),(0,2),(3,4),(3,5))])
            between=np.mean([np.linalg.norm(coords[a]-coords[b]) for a in range(3) for b in range(3,6)])
            self.assertLess(within,between)
        self.assertEqual(results,grouping_layouts(data))

if __name__=='__main__':unittest.main()
